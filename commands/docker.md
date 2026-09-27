# Docker Command Reference

## Images

```
docker images
docker pull <image>
docker build -t <name>:<tag> .
docker build -t <name>:<tag> -f Dockerfile.prod .
docker tag <image> <new-name>:<tag>
docker push <name>:<tag>
docker rmi <image>
docker image prune
docker image prune -a
docker history <image>
docker inspect <image>
```

## Containers

```
docker run <image>
docker run -d <image>
docker run -it <image> /bin/bash
docker run -p 8080:80 <image>
docker run -e KEY=value <image>
docker run -v /host/path:/container/path <image>
docker run --name my-container <image>
docker run --rm <image>
docker run --restart=always <image>
docker ps
docker ps -a
docker start <container>
docker stop <container>
docker restart <container>
docker kill <container>
docker rm <container>
docker rm -f <container>
docker logs <container>
docker logs -f <container>
docker logs --tail=100 <container>
docker exec -it <container> /bin/bash
docker exec -it <container> sh
docker inspect <container>
docker top <container>
docker stats
docker stats <container>
docker cp <container>:/path ./local
docker cp ./local <container>:/path
docker diff <container>
docker pause <container>
docker unpause <container>
docker rename <old> <new>
docker attach <container>
```

## Volumes

```
docker volume ls
docker volume create <name>
docker volume inspect <name>
docker volume rm <name>
docker volume prune
```

## Networks

```
docker network ls
docker network create <name>
docker network inspect <name>
docker network connect <network> <container>
docker network disconnect <network> <container>
docker network rm <name>
docker network prune
```

## Docker Compose

```
docker compose up
docker compose up -d
docker compose up --build
docker compose down
docker compose down -v
docker compose ps
docker compose logs
docker compose logs -f <service>
docker compose build
docker compose restart
docker compose restart <service>
docker compose exec <service> /bin/bash
docker compose config
docker compose pull
```

## System / Cleanup

```
docker system df
docker system prune
docker system prune -a
docker system prune --volumes
docker info
docker version
docker login
docker logout
```

## Dockerfile essentials (not commands, but you need to recognize these)

```
FROM <image>
WORKDIR /app
COPY . .
RUN <command>
ENV KEY=value
EXPOSE <port>
CMD ["executable", "arg"]
ENTRYPOINT ["executable"]
ARG <name>=<default>
USER <user>
VOLUME ["/data"]
HEALTHCHECK CMD curl -f http://localhost/ || exit 1
```

## Common debugging patterns

```
docker logs <container> --since 10m
docker exec -it <container> ps aux
docker exec -it <container> env
docker inspect <container> --format='{{.State.ExitCode}}'
docker inspect <container> --format='{{.NetworkSettings.IPAddress}}'
docker events
```
