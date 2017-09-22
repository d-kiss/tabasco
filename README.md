# tabasco
##### Time Based Source Control   -   A daemon monitoring the history of your work.
__tabasco__ is like git without the bother.
It creates commits of your code every so often and allows you to easily revert your code without you even knowing!
It consists of two components - the commands you can supply to interact with the system, and the daemon (```tabasco start```) running.

# Read the Docs
```
Usage:
    tabasco start [--frequency=<seconds>]
    tabasco stop
    tabasco monitor <directory>
    tabasco unmonitor <directory>
    tabasco log
    tabasco apply <commit>
    tabasco rm <commit>
    tabasco -h | --help
    tabasco --version

Options:
    -h, --help                  Show this help message.
    --version                   Show version.
    --frequency=<seconds>       how frequently to monitored
                                directories. [default: 5]
```

# Getting Started
Using __tabasco__ is as easy as running ```tabasco start &``` as a daemon and ```tabasco monitor <my_code_directory>``` from a shell.

# Issues
Take a look in our __issues__ tab!
