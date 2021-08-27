# umake

A minimal tool for build system for c++, it can automatically scan the dependencies (Now modules only, maybe source files for objects will be supported later soon) and add them.

And umake will cache the scanning results.

But well, now it only provides an extension for cmake.

## notice 

Please do not write codes like below to confuse me, especially when importing that would cause errors, such as cyclic import:

~~~cpp
#if 0
import somemodule;
#endif
~~~

## usage

First, you should clone this reposity or just download it.

Second, you should have a Python executable. Some packages are required, you can install them after you tried running umake.py.

### Together with CMake

Just include(umake.cmake), then replace your add_executable with add_main_source. For example,

~~~CMake
add_main_source("../umake/umake.py" main main.cpp tests tests.cpp)
~~~