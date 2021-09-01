# umake

A minimal tool for build system for c++, it can automatically scan the dependencies (not all dependencies can be found, now only C++20 modules import and intermediate objects) and add them.

As umake will cache the scanning results, you may want to delete it or disable it, should it caused errors. Configurations are supported but not enabled by default.

But well, now it only provides an extension for cmake. And not all compilers support cpp modules.

## notice 

Please avoid writting codes like below to confuse me, especially when importing that would cause errors, such as cyclic import:

~~~cpp
#if 0
import somemodule; 
#endif
~~~

Avoid double underlines in filename if you enable auto object dependencies detection, which is used for escaping for slash and back-slash.

Source file dependencies can't be recognized if you didn't include the corresponding headers, you can add them to dependencies manually if really needed.

## usage

First, you should clone this reposity or just download it.

Second, you should have a Python executable. Some packages are required, you can install them after you tried running umake.py.

### Together with CMake

Just include umake.cmake in your CMakeLists.txt, then replace your add_executable with add_main_source. For example, 

~~~CMake
add_moduled_executables_with_a_main_source("../umake/umake.py" main main.cpp tests tests.cpp)
~~~

Unless you have already run umake.py and let generate a umakeConfig.json on current directory, you should specify the path for umake.py. And be cautious that target name and source file should be given one for one.

It's recommended that you config umake with umakeConfig.json, which means you can have more umake features with cmake.

Moduled libraries are not tested.

If you delete a .ifc file without deleting its corresponding object, errors will occurred, you can clean and rebuild all or just delete corresponding object.

And if you use some generators other than Ninja, you may meet errors. If you don't like Ninja, you can try v0.0.0 version for higher compatibility.

Visual Studio may meet errors, such as .ifc files can't be deleted if you modify the codes in your project and build them several times, you can close VS and then delete them by yourselves. I didn't meet those problems when using Visual Studio Code.
