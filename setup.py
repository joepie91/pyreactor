from setuptools import setup

setup(name='pyreactor',
      version='0.1',
      description='Simple evented networking library, designed for custom protocols.',
      author='Sven Slootweg',
      author_email='pyreactor@cryto.net',
      url='http://cryto.net/pyreactor',
      packages=['pyreactor'],
      provides=['pyreactor'],
      install_requires=['msgpack-python']
     )
