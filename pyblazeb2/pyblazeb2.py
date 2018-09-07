# -*- coding: utf-8 -*-


import mmap
import time
import queue
import base64
import hashlib
import json
import os
import re
import threading
import urllib.request, \
       urllib.error, \
       urllib.parse
#
# #
# # Author: Mitch Long <mwlong23@gmail.com>
# #
# # A class for accessing the Backblaze B2 API
# #
# # All of the API methods listed are implemented:
# #   https://www.backblaze.com/b2/docs/


class PyBlazeB2(object):
    def __init__(self, account_id, app_key, mt_queue_size=12, valid_duration=24 * 60 * 60,
                 auth_token_lifetime_in_seconds=2 * 60 * 60, default_timeout=None):
        self.account_id = account_id
        self.app_key = app_key
        self.authorization_token = None
        self.api_url = None
        self.download_url = None
        self.upload_url = None
        self.upload_authorization_token = None
        self.valid_duration = valid_duration
        self.queue_size = mt_queue_size
        self.upload_queue = queue.Queue(maxsize=mt_queue_size)
        self.default_timeout = default_timeout
        self._last_authorization_token_time = None
        self.auth_token_lifetime_in_seconds = auth_token_lifetime_in_seconds,
        self.upload_queue = None,
        self.threads = None
        self.upload_queue_done = True

    def authorize_account(self, timeout=None):
        id_and_key = self.account_id + ':' + self.app_key
        b64_id_and_key = id_and_key.encode()
        basic_auth_string = 'Basic ' + base64.b64encode(b64_id_and_key).decode("utf-8")
        headers = {'Authorization': basic_auth_string}
        try:
            request = urllib.request.Request(
                'https://api.backblaze.com/b2api/v1/b2_authorize_account',
                headers=headers
            )
            response = self.__url_open_with_timeout(request, timeout)
            response_data = json.loads(response.read())
            response.close()
        except urllib.error.HTTPError as error:
            print(("ERROR: %s" % error.read()))
            raise

        self.authorization_token = response_data['authorizationToken']
        self._last_authorization_token_time = time.time()
        self.api_url = response_data['apiUrl']
        self.download_url = response_data['downloadUrl']
        return response_data

    def _authorize_account(self, timeout):
        if (self._last_authorization_token_time is not None \
            and time.time() - self._last_authorization_token_time > self.auth_token_lifetime_in_seconds) \
                or not self.authorization_token or not self.api_url:
            self.authorize_account(timeout)

    def __url_open_with_timeout(self, request, timeout):
        if timeout is not None or self.default_timeout is not None:
            custom_timeout = timeout or self.default_timeout
            response = urllib.request.urlopen(request, timeout=custom_timeout)
        else:
            response = urllib.request.urlopen(request)
        return response

    def create_bucket(self, bucket_name, bucket_type='allPrivate', timeout=None):
        self._authorize_account(timeout)
        # bucket_type can be Either allPublic or allPrivate
        return self._api_request('%s/b2api/v1/b2_create_bucket' % self.api_url,
                                 {'accountId': self.account_id,
                                  'bucketName': bucket_name,
                                  'bucketType': bucket_type},
                                 {'Authorization': self.authorization_token}, timeout)

    def get_download_authorization(self, bucket_id, bucket_name,
                                   file_name_prefix, timeout):
        self._authorize_account(timeout)
        url = '%s/b2api/v1/b2_get_download_authorization' % self.api_url
        data = {
            'bucketId': bucket_id,
            'fileNamePrefix': file_name_prefix,
            'validDurationInSeconds': self.valid_duration
        }
        result = self._api_request(
            url,
            data,
            {'Authorization': self.authorization_token},
            timeout
        )
        url_authorized_download = "{}/file/{}/{}?Authorization={}".format(
            self.download_url, bucket_name, result['fileNamePrefix'],
            result['authorizationToken']
        )

        return url_authorized_download

    def list_buckets(self, timeout=None):
        self._authorize_account(timeout)
        return self._api_request('%s/b2api/v1/b2_list_buckets' % self.api_url,
                                 {'accountId': self.account_id},
                                 {'Authorization': self.authorization_token}, timeout)

    def get_bucket_info(self, bucket_id=None, bucket_name=None, timeout=None):
        bkt = None
        if not bucket_id and not bucket_name:
            raise Exception(
                "get_bucket_info requires either a bucket_id or bucket_name")
        if bucket_id and bucket_name:
            bucket_name = None

        buckets = self.list_buckets(timeout)['buckets']
        if not bucket_id:
            key = 'bucketName'
            val = bucket_name
        else:
            key = 'bucketId'
            val = bucket_id
        for bucket in buckets:
            if bucket[key] == val:
                bkt = bucket
                break
        return bkt

    def delete_bucket(self, bucket_id=None, bucket_name=None, timeout=None):
        if not bucket_id and not bucket_name:
            raise Exception(
                "delete_bucket requires either a bucket_id or bucket_name")
        if bucket_id and bucket_name:
            raise Exception(
                "delete_bucket requires only _one_ argument and not both bucket_id and bucket_name")
        self._authorize_account(timeout)
        bucket = self.get_bucket_info(bucket_id, bucket_name, timeout)
        return self._api_request('%s/b2api/v1/b2_delete_bucket' % self.api_url,
                                 {'accountId': self.account_id,
                                  'bucketId': bucket['bucketId']},
                                 {'Authorization': self.authorization_token}, timeout)

    def get_upload_url(self, bucket_name=None, bucket_id=None, timeout=None):
        self._authorize_account(timeout)
        bucket = self.get_bucket_info(bucket_id, bucket_name)
        bucket_id = bucket['bucketId']
        return self._api_request('%s/b2api/v1/b2_get_upload_url' % self.api_url,
                                 {'bucketId': bucket_id},
                                 {'Authorization': self.authorization_token}, timeout)

    def upload_file(self, path, filename=None, bucket_id=None, bucket_name=None,
                    thread_upload_url=None,
                    thread_upload_authorization_token=None, timeout=None):

        self._authorize_account(timeout)

        mm_file_data = None
        try:
            fp = open(path, 'rb')
            mm_file_data = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
            filename = re.sub('^/', '', filename)
            filename = re.sub('//', '/', filename)

        except Exception as e:
            print("Can't resolve file path: {0}".format(e))

        # Use buffers to not use tons of memory when uploading large files
        # https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
        sha = hashlib.sha1()
        with open(path, 'rb') as f:
            while True:
                block = f.read(2 ** 10)
                if not block:
                    break
                sha.update(block)
        sha = sha.hexdigest()

        if thread_upload_url:
            cur_upload_url = thread_upload_url
            cur_upload_authorization_token = thread_upload_authorization_token

        elif not self.upload_url or not self.upload_authorization_token:
            url = self.get_upload_url(bucket_name=bucket_name,
                                      bucket_id=bucket_id)
            cur_upload_url = url['uploadUrl']
            cur_upload_authorization_token = url['authorizationToken']

        # if no filename is specified, use local path
        if not filename:
            filename = os.path.basename(path)

        # All the whitespaces in the filename should be converted to %20

        # https://stackoverflow.com/questions/1695183/how-to-percent-encode-url-parameters-in-python
        filename = urllib.parse.quote(filename, safe='')

        content_length = os.path.getsize(path)

        headers = {
            'Authorization': cur_upload_authorization_token,
            'X-Bz-File-Name': filename,
            'Content-Length': content_length,
            'Content-Type': 'b2/x-auto',
            'X-Bz-Content-Sha1': sha
        }
        try:
            request = urllib.request.Request(cur_upload_url, mm_file_data, headers)
            response = self.__url_open_with_timeout(request, timeout)
            response_data = json.loads(response.read())
        except urllib.error.HTTPError as error:
            print(("ERROR: %s" % error.read().decode('utf-8')))
            raise

        response.close()
        fp.close()
        return response_data

    """Modifies the bucketType of an existing bucket
    Used to allow downloading without authorization or
    prevent downloading without authorization"""

    def update_bucket(self, bucket_type, bucket_id=None, bucket_name=None, timeout=None):
        if bucket_type not in ('allPublic', 'allPrivate'):
            raise Exception(
                "update_bucket: Invalid bucket_type.  Must be string allPublic or allPrivate")

        bucket = self.get_bucket_info(bucket_id=bucket_id,
                                      bucket_name=bucket_name, timeout=timeout)
        return self._api_request('%s/b2api/v1/b2_update_bucket' % self.api_url,
                                 {'bucketId': bucket['bucketId'],
                                  'bucketType': bucket_type},
                                 {'Authorization': self.authorization_token}, timeout)

    def list_file_names(self, bucket_id=None, bucket_name=None, maxFileCount=100, startFileName=None, prefix=None,
                        timeout=None):
        bucket = self.get_bucket_info(bucket_id=bucket_id,
                                      bucket_name=bucket_name, timeout=timeout)
        if maxFileCount > 10000:
            maxFileCount = 10000

        if maxFileCount < 0:
            maxFileCount = 100

        data = {'bucketId': bucket['bucketId'], 'maxFileCount': maxFileCount}

        if startFileName is not None:
            data['startFileName'] = startFileName
        if prefix is not None:
            data['prefix'] = prefix

        return self._api_request(
            '%s/b2api/v1/b2_list_file_names' % self.api_url,
            data,
            {'Authorization': self.authorization_token}, timeout)

    def delete_file_version(self, file_name, file_id, timeout=None):
        return self._api_request(
            '%s/b2api/v1/b2_delete_file_version' % self.api_url,
            {'fileName': file_name, 'fileId': file_id},
            {'Authorization': self.authorization_token}, timeout)

    def get_file_info_by_name(self, file_name, bucket_id=None, bucket_name=None):
        file_names = self.list_file_names(bucket_id=bucket_id, bucket_name=bucket_name, prefix=file_name)
        for i in file_names['files']:
            if file_name in i['fileName']:
                return self.get_file_info(i['fileId'])
        return None

    def get_file_info(self, file_id, timeout=None):
        return self._api_request('%s/b2api/v1/b2_get_file_info' % self.api_url,
                                 {'fileId': file_id},
                                 {'Authorization': self.authorization_token}, timeout)

    def download_file_with_authorized_url(self, url, dst_file_name, force=False, timeout=None):
        #TODO: Windows path compatability
        if os.path.exists(dst_file_name) and not force:
            raise Exception(
                "Destination file exists. Refusing to overwrite. "
                "Set force=True if you wish to do so.")
        request = urllib.request.Request(
            url, None, {})
        response = self.__url_open_with_timeout(request, timeout)

        # TODO: default downloaded files to downloads folder
        return PyBlazeB2.write_file(response, dst_file_name)

    def download_file_by_name(self, file_name, dst_file_name, bucket_id=None,
                              bucket_name=None, force=False, timeout=None):
        if os.path.exists(dst_file_name) and not force:
            raise Exception(
                "Destination file exists. Refusing to overwrite. "
                "Set force=True if you wish to do so.")

        self._authorize_account(timeout)
        bucket = self.get_bucket_info(bucket_id=bucket_id,
                                      bucket_name=bucket_name, timeout=timeout)

        url = self.download_url + '/file/' + bucket[
            'bucketName'] + '/' + file_name

        headers = {
            'Authorization': self.authorization_token
        }

        request = urllib.request.Request(
            url, None, headers)
        response = self.__url_open_with_timeout(request, timeout)

        return PyBlazeB2.write_file(response, dst_file_name)

    def download_file_by_id(self, file_id, dst_file_name, force=False, timeout=None):
        if os.path.exists(dst_file_name) and not force:
            raise Exception(
                "Destination file exists. Refusing to overwrite. "
                "Set force=True if you wish to do so.")

        self._authorize_account(timeout)
        url = self.download_url + '/b2api/v1/b2_download_file_by_id?fileId=' + file_id
        request = urllib.request.Request(url, None,
                                         {'Authorization': self.authorization_token})
        resp = self.__url_open_with_timeout(request, timeout)
        return PyBlazeB2.write_file(resp, dst_file_name)

    def _upload_worker(self, bucket_id, bucket_name):
        # B2 started requiring a unique upload url per thread
        """Uploading in Parallel
        The URL and authorization token that you get from b2_get_upload_url can be used by only one thread at a time.
        If you want multiple threads running, each one needs to get its own URL and auth token. It can keep using that
        URL and auth token for multiple uploads, until it gets a returned status indicating that it should get a
        new upload URL."""
        url = self.get_upload_url(bucket_name=bucket_name, bucket_id=bucket_id)
        thread_upload_url = url['uploadUrl']
        thread_upload_authorization_token = url['authorizationToken']

        while not self.upload_queue_done:
            time.sleep(1)
            try:
                path = self.upload_queue.get_nowait()
            except:
                continue
            # try a few times in case of error
            for i in range(4):
                try:
                    self.upload_file(path,
                                     bucket_id=bucket_id,
                                     bucket_name=bucket_name,
                                     thread_upload_url=thread_upload_url,
                                     thread_upload_authorization_token=thread_upload_authorization_token)
                    break
                except Exception as e:
                    print((
                            "WARNING: Error processing file '%s'\n%s\nTrying again." % (
                        path, e)))
                    time.sleep(1)

    def recursive_upload(self, path, bucket_id=None, bucket_name=None,
                         exclude_regex=None, include_regex=None,
                         exclude_re_flags=None, include_re_flags=None,
                         multithread=True):
        bucket = self.get_bucket_info(bucket_id=bucket_id,
                                      bucket_name=bucket_name)
        if exclude_regex:
            exclude_regex = re.compile(exclude_regex, flags=exclude_re_flags)
        if include_regex:
            include_regex = re.compile(include_regex, flags=include_re_flags)

        nfiles = 0
        if os.path.isdir(path):
            if multithread:
                # Generate Queue worker threads to match QUEUE_SIZE
                self.threads = []
                self.upload_queue_done = False
                for i in range(self.queue_size):
                    t = threading.Thread(target=self._upload_worker, args=(
                        bucket_id, bucket_name,))
                    self.threads.append(t)
                    t.start()

            for root, dirs, files in os.walk(path):
                for f in files:
                    if os.path.islink(root + '/' + f): continue
                    if exclude_regex and exclude_regex.match(
                            root + '/' + f): continue
                    if include_regex and not include_regex.match(
                            root + '/' + f): continue
                    if multithread:
                        print(("UPLOAD: %s" % root + '/' + f))
                        self.upload_queue.put(root + '/' + f)
                    else:
                        self.upload_file(root + '/' + f,
                                         bucket_id=bucket_id,
                                         bucket_name=bucket_name)
                    nfiles += 1
            if multithread:
                self.upload_queue_done = True
                for t in self.threads:
                    t.join()

        else:
            nfiles = 1
            if not os.path.islink(path):
                if exclude_regex and exclude_regex.match(path):
                    nfiles -= 1
                if include_regex and include_regex.match(path):
                    nfiles += 1
            if nfiles > 0:
                print(("UPLOAD: %s" % path))
                self.upload_file(path, bucket_id=bucket_id,
                                 bucket_name=bucket_name)
                return 1
            else:
                print("WARNING: No files uploaded")
        return nfiles

    def _api_request(self, url, data, headers, timeout=None):
        self._authorize_account(timeout)
        request = urllib.request.Request(url, json.dumps(data).encode('utf-8'), headers)
        response = self.__url_open_with_timeout(request, timeout)
        response_data = json.loads(response.read())
        response.close()
        return response_data

    @staticmethod
    def write_file(response, dst_file_name):
        with open(dst_file_name, 'wb') as f:
            while True:
                chunk = response.read(2 ** 10)
                if not chunk:
                    break
                f.write(chunk)
            f.close()
        return True

