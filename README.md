# Intensity Calculator for Phyphox
by HanZero

## 简介
本程序可将由phyphox app（官网：https://phyphox.org ）记录的加速度数据（需导出为csv文件）计算成相应的地震烈度（CSIS与JMA两种标准）并输出到控制台，支持实时监测和分析记录好的文件。

## 关于
许可证：MIT License
GitHub仓库：https://github.com/Han0HanZero/intensityCalculatorForPhyphox
蓝奏云发布地址：https://hanice.lanzouo.com/b01g0x7ra 密码:0721

开发环境Python版本：3.11.1

感谢滤波算法：https://zhuanlan.zhihu.com/p/615455014 ，潘超
开发中参考了GB/T 17742-2020《中国地震烈度表》、日本气象厅官网（https://www.data.jma.go.jp/eqev/data/kyoshin/kaisetsu/calc_sindo.html ）和中文维基百科等，但计算方法与之所述可能不完全相同。

本程序与亚琛工业大学及其附属机构无关。

## 使用方法
### 实时监控模式的使用

1. 在你的移动设备上下载phyphox，并打开它。
2. 将你的移动设备与电脑连接至同一局域网下，或让电脑连接至移动设备的热点。
3. 进入phyphox中的“加速度（不含g）”（注意：不是“含（g）的加速度”）。
4. 点击右上角省略号，在菜单中选择“启用远程访问”，点击“确认”。
5. 在电脑上双击main.exe打开程序，输入0，并回车。
6. 输入你的设备上显示的IP地址，并回车。
7. 记录应该会在几秒后自动开始。
8. 要停止记录，直接关闭main.exe/关闭phyphox/暂停实验/关闭网络即可。按Enter退出。

### 数据分析模式的使用

#### 导入手机上记录的数据
1. 在你的移动设备上下载phyphox，并打开它。
2. 进入phyphox中的“加速度（不含g）”（注意：不是“含（g）的加速度”）。
3. 开始实验，获取到足够的数据后，暂停实验。
4. 点击右上角省略号，在菜单中选择“导出数据”，在对话框中选择“CSV (Comma, decimal point)”，并点击“导出数据”。
5. 将导出的压缩包发送到电脑上，并解压。
6. 在电脑上双击main.exe打开程序，输入1，并回车。
7. 输入解压出的文件夹的路径（文件夹名应为：g xxxx-xx-xx xx-xx-xx），并回车。
8. 查看数据。查看结束后，关闭图像窗口，按Enter退出。

#### 导入实时监控模式记录的数据
1. 在电脑上双击main.exe打开程序，输入1，并回车。
2. 输入解压出的文件夹的路径（它应该储存在程序根目录/logs中，文件夹名应为：xxxxxxxxxxxxxx），并回车。
3. 查看数据。查看结束后，关闭图像窗口，按Enter退出。