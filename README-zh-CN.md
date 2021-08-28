# umake

一个用于C++构建系统的最小化工具，可以自动扫描依赖（目前只支持模块依赖，未来可能很快支持.obj依赖）。当前只提供cmake的插件。

配置文件和扫描缓存均为可选内容，但前者默认禁用，后者默认启用。

## 注意事项

请不要使用一些可能会导致错误的代码表达，umake将在标准内尽可能提供正确的行为。

## 使用

### 用于CMake

如例。

~~~CMake
include(../umake/umake.cmake)
add_main_source("../umake/umake.py" main main.cpp tests tests.cpp)
~~~
