package main

import rego.v1

# Política como código (Conftest/OPA) para Dockerfiles.
deny contains msg if {
	some i
	input[i].Cmd == "from"
	val := input[i].Value[0]
	endswith(val, ":latest")
	msg := sprintf("Não use a tag :latest (%s)", [val])
}

deny contains msg if {
	not has_user
	msg := "Dockerfile sem instrução USER: o contêiner rodaria como root"
}

deny contains msg if {
	some i
	input[i].Cmd == "add"
	msg := "Prefira COPY a ADD"
}

has_user if {
	some i
	input[i].Cmd == "user"
	input[i].Value[0] != "root"
}
