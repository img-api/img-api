
# VISUAL STUDIO CODE

Our development instance is running here:
http://dev.gputop.com:8080/?folder=/home/dev/img-api

# API Entry points

## Site map
This will give you all the API entry points to explore the syntax and format
https://dev.gputop.com/api/admin/site-map

## Hello world
Check if the API responds to calls:
https://dev.gputop.com/api/hello_world/

It will return a standard message with the message "hello world".
Every call has a status so we can show success or failure with an error.
The UI will always have to check for this status.

```
    {
        api: "0.50pa",
        current_user: "contact@engineer.blue",
        msg: "hello world",
        status: "success",
        time: "2024-08-27 08:53:43.564692",
        timestamp: 1724748823
    }
```

# COMPANY API

## How to query documentation
https://docs.mongoengine.org/guide/querying.html

## Queries examples
https://dev.gputop.com/api/company/query?founded=1994

## Find company by name
https://gputop.com/api/company/query?company_name__icontains=nordisk

## Get all companies
https://dev.gputop.com/api/company/get/ALL

## Delete all companies in development
https://dev.gputop.com/api/company/rm/ALL

# FETCHES

This slow query will fetch everything.
https://dev.gputop.com/api/index/process