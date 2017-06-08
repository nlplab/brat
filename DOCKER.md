# Docker Tutorial
1. Download and install docker.
2. Clone the simstring-1.1 project. `git clone https://github.com/chokkan/simstring.git`
3. Build the docker image `docker build -t brat .`
4. Then run the docker image with `docker run -p 80:8000 -it --rm -v /home/maggiel/brat:/app/brat brat`.
5. `-p 80:8000` will map port 80 locally to the container's 8000.
6. `-v TARGET:TARGET_ON_IMAGE` will map your local storage TARGET to the directory TARGET_ON_IMAGE on the image. So you can use this to develop quickly without rebuilding the image multiple times.