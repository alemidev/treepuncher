from setuptools import setup, find_packages

with open("requirements.txt") as f:
	requirements = f.read().split("\n")

setup(
	name='treepuncher',
	version='0.0.1',
	description='An hackable Minecraft client, built with aiocraft',
	url='https://github.com/alemidev/treepuncher',
	author='alemi',
	author_email='me@alemi.dev',
	license='MIT',
	packages=find_packages(),
	package_data = {
		'treepuncher': ['py.typed'],
	},
	install_requires=requirements,
	classifiers=[
		'Development Status :: 1 - Planning',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',  
		'Operating System :: POSIX :: Linux',		 
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.8',
	],
)
