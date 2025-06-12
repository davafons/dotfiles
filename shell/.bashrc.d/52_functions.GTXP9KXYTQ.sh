
start_colima() {
  local CERTS="${HOME}/.ca-certificates"
  local URL="registry-1.docker.io:443"
  mkdir -p ${CERTS}
  cp -f '/Library/Application Support/Netskope/STAgent/download/nscacert_combined.pem' ${CERTS}
  openssl s_client -showcerts -connect ${URL} </dev/null 2>/dev/null|openssl x509 -outform PEM >${CERTS}/docker-com.pem
  openssl s_client -showcerts -verify 5 -connect ${URL} </dev/null 2>/dev/null | sed -ne '/-BEGIN/,/-END/p' >${CERTS}/docker-com-chain.pem
  # colima start --memory 8 --cpu 2 --vm-type=vz --mount-type=virtiofs --network-address --vz-rosetta
  colima start -t qemu --cpu 2 --memory 8 --disk 80 --mount-type=virtiofs --network-address --edit

  colima ssh -- sudo cp ${CERTS}/* /usr/local/share/ca-certificates/
  colima ssh -- sudo update-ca-certificates
  colima ssh -- sudo service docker restart
}
