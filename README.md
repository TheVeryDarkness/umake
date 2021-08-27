# umake

A minimal tool for build system for c++. Well, now it only provides an extension for cmake.

## notice 

Please do not write codes like below to confuse me, especially when importing that would cause errors, such as cyclic import:

~~~cpp
#if 0
import somemodule;
#endif
~~~