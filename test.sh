flake8 --config=config/flake8rc *.py
pylint --rcfile=config/pylintrc *.py
python3 -m unittest discover
