python3:
	python setup.py sdist

upload: python3
	twine upload dist/*

image:
	docker-compose run --rm packer packer build ./e2e/packer.json

e2e:
	docker-compose run --rm python python3 ./e2e/e2e.py

venv:
	python3 -m venv --copies venv
	sed -i '43s/.*/VIRTUAL_ENV="$$(cd "$$(dirname "$$(dirname "$${BASH_SOURCE[0]}" )")" \&\& pwd)"/' venv/bin/activate
	sed -i '1s/.*/#!\/usr\/bin\/env python/' venv/bin/pip*
