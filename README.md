# Reddit Stock Webscrapper

## What it does

1. Scrap /r/wallstreetbets for yesterday's Daily Discussion
2. Gather all comment ids
3. Use [pushshift API](https://github.com/pushshift/api) to get comment text
4. Count stock ticket mentions in all comments
5. Write results to a csv

## TODO

- Gather current stock tickets on a monthly? interval
- Run daily lambda function and write to s3 bucket

Export the project dependencies as requirements.txt
`poetry export -f requirements.txt > requirements.txt --without-hashes`

GoLang version coming soon...
