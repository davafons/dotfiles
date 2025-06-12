grbo() {
  git rebase --onto "$1" "$2^" "$2"
}

gbaco() {
  git branch -f "$1" && git checkout "$1"
}

gfr() {
  git reset @~ "$@" && git commit --amend --no-edit
}

killport() {
  kill -9 $(lsof -i:$1)
}

b64() {
  echo -n "$1" | base64
}

db64() {
  echo -n "$1" | base64 --decode
}

wiped() {
  # stop and !! REMOVE !! all containers (looses all data inside containers)
  docker ps | awk '{print $1}' | grep -v CONTAINER | xargs docker stop && \
  docker ps -a | awk '{print $1}' | grep -v CONTAINER | xargs docker rm
}
