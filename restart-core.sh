docker stop vismay-core-bckend-container
docker rm vismay-core-bckend-container
docker build -t vismay-core-bckend .

docker run -d -p 8000:8000 --name vismay-core-bckend-container vismay-core-bckend
