image:
	docker-compose run --rm packer packer build packer.json

e2e:
	docker-compose run --rm python python3 ./e2e.py
