### Build image: docker build -t cogn .

### Run: docker run -v $PWD:/cogn cogn -n -s 100

### This will create the results.json

Command line flag | Description
------------ | -------------
-n, --noisy_mode | Enable noisy mode
-s SERIES_SIZE | Number of matrices (100 each)
