# Introduction to Pyblazeb2 
---------------

    Pyblazeb2 is a Python 3 module for storage bucket manipulation and session management through Backblaze B2 API.
    
    Easily create buckets, upload files and authenticate with one lightweight module.
    
    To install run: 
        
```python 
     pip install pyblazeb2
```

  ##Authenticate Your account
  
    Use your credentials provided by Backblaze to create a pyblaze object.  
      
```python
    from pyblazeb2 import BackBlazeB2
    
    b2 = PyBlazeB2(account_id, app_key)
``` 
    
#Upload Files/folders
   
  ##Upload an entire directory concurrently
    recursive_upload(path, bucket_id || bucket_name, [multithread]
    
    Upload an entire directory, any subdirecories and any files within. 
    Either a bucket name or bucket id is required as a target for your files.
    If the bucket name or id is not known, the list_buckets and get_bucket_info methods
    can be used to retrieve details(see below).
    
```python
    b2.recursive_upload('/path/to/directory', bucket_name='my-bucket', multithread=True)
```
    
  ##Upload a single file
  
    upload_file(filepath, bucket_name)
    
    Upload a single file using the local path to a target file and a destination bucket.
    
```python
    b2.upload_file('/path/to/file.txt', bucket_name='marketing-content')
```
    
#Download Files
   
   ##Download a single file
   
    download_file_by_name(local_destination, file_name, bucket_name || bucket_id)
    
    Single files can be downloaded by bucket name or Id. A Local destination must be provided, 
    along with the name of the file to download.
    
```python 
    response = b2.download_file_by_name('/path/to/myfile.txt', 'savedfile.txt', bucket_name='cat-videos')
```
    
   ## Authorize download for a private file
   
    
    get_download_authorization(bucket_name='' || bucket_id='', file_name_prefix = "")
    
    Download a private file by specifying either the bucket name or id  and providing a file name 
    with a file extension(.mpg, .mp4, ect.).
     
```python
        url_authorized_download = b2.get_download_authorization(
        bucket_id=bucket_id, bucket_name=bucket_name,
        file_name_prefix=file_name_prefix)
```

   ## Download with authorized url
   
    b2.download_file_with_authorized_url(url_authorized_download, 'file_name.log')
    
#Read Bucket Details

    ## List all of your buckets
    
    buckets = b2.list_buckets()
    
    ## Check Bucket_details
    
    Retrieve the following properties from a bucket:
        bucket_id
        bucket_name
        bucket_type
        bucket_info
        lifecycle_rules
        revision
        cors_rules
        deleted
     
    get_bucket_info(bucket_id='' || bucket_name='')
```python
    b2.get_bucket_info(bucket_name='legal-documents')

```
        
    ## Create a bucket
    
    Add a new bucket, specifiy a name and permissions(allPrivate or allPublic).
    
    response = b2.create_bucket('new-bucket', bucket_type='allPrivate')
    
##Support
    At the moment, Windows is not supported by Pyblaze. Pull requests are welcome.
    
    
 #### This software is covered by the MIT license 
    