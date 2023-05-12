from setuptools import setup, find_packages


def parse_requirements(req_file):
    with open(req_file) as fp:
        _requires = fp.read()
    return _requires


NAME = "panoptic"
VERSION = "0.0.1"
# Get dependencies from requirement files
SETUP_REQUIRES = ['setuptools', 'setuptools-git', 'wheel']
INSTALL_REQUIRES = parse_requirements('requirements.txt')


def setup_package():
    metadata = dict(name=NAME,
                    version=VERSION,
                    install_requires=INSTALL_REQUIRES,
                    setup_requires=SETUP_REQUIRES,
                    packages=find_packages())

    setup(**metadata)


if __name__ == "__main__":
    setup_package()