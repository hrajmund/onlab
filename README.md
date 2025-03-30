### Initialize with docker

docker build -t controller_py .
docker run -it --rm -p 8051:8051 controller_py

#### Alongside

./build.sh

#### Test build's connection
curl -X 'POST' \
  '.../out-of-band/create-invitation' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "handshake_protocols": ["https://didcomm.org/didexchange/1.0"]
}'

##### OR

{
  "handshake_protocols": ["https://didcomm.org/didexchange/1.0"]
}

#### Run docker locally

http://host.docker.internal:8051/webhooks