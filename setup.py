from setuptools import setup


with open('LICENSE') as f:
    license = f.read().splitlines()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()


setup(
    name='note',
    version='0.1.0',
    url='https://github.com/wsw70/note',
    download_url='https://github.com/wsw70/note/archive/master.zip',
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: The Unlicense (Unlicense)',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
    license=license,
    description='A command-line based note-taking app',
    keywords=[
        'Notes',
    ],
    zip_safe=True,
    py_modules=[
        'note',
    ],
    install_requires=requirements,
    entry_points=dict(
        console_scripts=[
            'note = note',
        ],
    ),
)
