from setuptools import setup, find_packages
import os

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
                    licence='MIT',
                    install_requires=INSTALL_REQUIRES,
                    setup_requires=SETUP_REQUIRES,
                    entry_points={
                        'console_scripts':[
                            'panoptic = panoptic.main:start'
                        ]
                    },
                    include_package_data=True,
                    # package_dir="panoptic/html",
                    package_data={
                        "": ['html/*', 'html/assets/*'],
                    },
                    packages=find_packages())

    setup(**metadata)


def _copy_html_data(directory):
    base_dir = os.path.join('', directory)
    for (dirpath, dirnames, files) in os.walk(base_dir):
        for f in files:
            yield os.path.join(dirpath.split('/', 1)[1], f)

if __name__ == "__main__":
    setup_package()