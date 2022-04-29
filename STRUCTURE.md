# APPLICATION STRUCTURE

See REQUIREMENTS.md for an explanation on functional requirements

## API
    Using an API Token the user can get access to the site

## APP
    Renders our HTML to help users navigate the site, preview and view images

## ADMIN
    User validation, content approval and removal

## UNIT TESTING
    We use pytest to run a battery of tests on the working functional site
    run_test.sh

## DATA STORAGE
    We use MongoDB as our database
    Collections definitions TBD

## MICROSERVICES
    Website runs services on demand, it queries offline services with jobs to perform the different image processing tasks.
    Those jobs will be processed by shell or python commands.

    They will use a REDIS server for this purpose.
