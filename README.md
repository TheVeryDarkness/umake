# umake

A minimal tool for build system for c++.

Please do not write codes like below to confuse me, especially when importing that would cause errors, such as cyclic import:

~~~cpp
#if 0
import somemodule;
#endif
~~~