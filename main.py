import csv
from math import log10,sqrt
from scipy import signal
import matplotlib.pyplot as plt
import numpy as np
from requests import get
from time import strftime, gmtime, sleep
from os import mkdir
import json
from os import sep


def throw_an_error(errmsg, stop:bool = True):
    """stop：为真时程序将退出"""
    print('发生错误：'+errmsg)
    if stop:
        input('因为此错误，程序无法继续运行，按Enter退出...')
        exit(1)


def init_folders():
    try:
        mkdir('./logs')
    except FileExistsError:
        pass
    except Exception as e:
        throw_an_error(e, True)


def get_config():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        return config


def get_meta(ip):
    device = get(ip + '/meta').text
    start_time = strftime('%Y%m%d%H%M%S', gmtime())  # UTC
    mkdir('./logs/'+start_time)
    with open('./logs/'+start_time+'/meta.json', 'x') as meta_file:
        meta_file.write(device)
    return start_time


def analyse_raw_data(start_time, last_latest_time, ip):  # 解析原始数据并存储。每隔3秒从上回的latest位置到这回的latest位置获取数据（即acc_time），避免数据缺失
    response = get(f'{ip}/get?accX={last_latest_time}|acc_time&accY={last_latest_time}|acc_time&accZ={last_latest_time}|acc_time&acc={last_latest_time}|acc_time&acc_time={last_latest_time}')
    response_json = response.json()['buffer']
    raw_data_t = response_json['acc_time']['buffer']  # 原时间数据序列
    raw_data_x = response_json['accX']['buffer']  # 原x方向数据序列
    raw_data_y = response_json['accY']['buffer']  # 原y方向数据序列
    raw_data_z = response_json['accZ']['buffer']  # 原z方向数据序列
    raw_data_a = response_json['acc']['buffer']  # 原合成数据序列
    try:  # 判断文件是否存在来决定是否添加表头
        open(f'./logs/{start_time}/Raw Data.csv', 'r')
    except FileNotFoundError:
        file_exists = False
    else:
        file_exists = True
    with open(f'./logs/{start_time}/Raw Data.csv', 'a', newline='') as csv_file:
        writer = csv.writer(csv_file, delimiter=',')
        if not file_exists:
            writer.writerow(['Time (s)', 'Linear Acceleration x (m/s^2)', 'Linear Acceleration y (m/s^2)', 'Linear Acceleration z (m/s^2)', 'Absolute acceleration (m/s^2)'])
        for t,x,y,z,a in zip(raw_data_t,raw_data_x,raw_data_y,raw_data_z,raw_data_a):
            writer.writerow([t,x,y,z,a])
    last_latest_time = raw_data_t[-1]
    is_measuring = response.json()['status']['measuring']
    return last_latest_time, raw_data_t, raw_data_x, raw_data_y, raw_data_z, raw_data_a, is_measuring  # TODO:明天该做每三秒的滤波 数据合成 震度估测了


def filter_wave(x, dt=0.01, fl=0.1, fh=10, btype="bandpass", order=4):  # https://zhuanlan.zhihu.com/p/615455014
    '''
    滤波\\
    参数含义：
    x: 信号序列
    dt: 信号的采样时间间隔
    fl: 滤波截止频率（低频）
    fh: 滤波截止频率（高频）
    btype: 滤波器类型
        "lowpass": 低通（保留低于fh的频率成分）
        "highpass": 高通（保留高于fl的频率成分）
        "bandpass": 带通（保留fl~fh之间的频率成分）
        "bandstop": 带阻（过滤fl~fh之间的频率成分）
    '''
    fn = 1.0 / dt / 2.0  # 奈奎斯特频率

    if btype == "lowpass":
        Wn = fh / fn
    elif btype == "highpass":
        Wn = fl / fn
    elif btype == "bandpass" or btype == "bandstop":
        Wn = (fl / fn, fh / fn)

    b, a = signal.butter(order, Wn, btype)
    y = signal.filtfilt(b, a, x)

    return y


def csis_calc(a,v,csis_v):
    ia = 3.17 * log10(a) + 6.59
    if csis_v:
        iv = 3.00 * log10(v) + 9.77
    else:
        iv = ia
    if ia >= 6.0 and iv >= 6.0:
        ii = (ia+iv)/2
    else:
        ii = ia
    ii = round(ii,1)
    if ii < 1.0:
        ii = 1.0
    elif ii > 12.0:
        ii = 12.0
    i = round(ii)
    return ii,i


def jma_calc(a):
    ia = 2 * log10(a) + 4.94
    ia = round(ia,2)
    ia = int(ia*10)/10
    if ia <= 0.4:
        i = 0
    elif ia <= 1.4:
        i = 1
    elif ia <= 2.4:
        i = 2
    elif ia <= 3.4:
        i = 3
    elif ia <= 4.4:
        i = 4
    elif ia <= 4.9:
        i = 5  # 5弱。最大震度筛选需要大小比较，于是用5代替。
    elif ia <= 5.4:
        i = 5.5  # 5强。最大震度筛选需要大小比较，于是用5代替。下同
    elif ia <= 5.9:
        i = 6
    elif ia <= 6.4:
        i = 6.5
    else:
        i = 7
    return ia,i


def format_i_jma(i_jma):
    """将5,5.5,6,6.5格式化为5-/+,6-/+，以便显示"""
    int_i = int(i_jma)
    if int_i == 5 or int_i == 6:
        if i_jma - int_i == 0.5:
            i_jma = str(int_i)+'+'
        else:
            i_jma = str(int_i)+'-'
    else:
        i_jma = str(i_jma)
    return i_jma

def save_processed_data(start_time, last_latest_time, processed_data: tuple, data_type: str):  # 存储处理后的数据
    """processed_data: (时间,ax,ay,az,a合成,类型v速度/a加速度)"""
    raw_data_t = processed_data[0]  # 原时间数据序列
    data_x = processed_data[1]  # 原x方向数据序列
    data_y = processed_data[2]  # 原y方向数据序列
    data_z = processed_data[3]  # 原z方向数据序列
    data_a = processed_data[4]  # 原合成数据序列
    if data_type == 'v':
        data_type = 'Velocity'
        unit = 'm/s'
    elif data_type == 'a':
        data_type = 'Linear Acceleration'
        unit = 'm/s^2'
    try:  # 判断文件是否存在来决定是否添加表头
        open(f'./logs/{start_time}/Processed Data ({data_type}).csv', 'r')
    except FileNotFoundError:
        file_exists = False
    else:
        file_exists = True
    with open(f'./logs/{start_time}/Processed Data ({data_type}).csv', 'a', newline='') as csv_file:
        writer = csv.writer(csv_file, delimiter=',')
        if not file_exists:
            writer.writerow(['Time (s)', f'{data_type} x ({unit})', f'{data_type} y ({unit})', f'{data_type} z ({unit})', f'Absolute {data_type} ({unit})'])
        for t,x,y,z,a in zip(raw_data_t,data_x,data_y,data_z,data_a):
            writer.writerow([t,x,y,z,a])
    last_latest_time = raw_data_t[-1]
    return last_latest_time, raw_data_t, data_x, data_y, data_z, data_a

def main_process(choice, processed, sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, a_max, v_max, a_max_time, v_max_time, ia_csis, i_csis, ia_jma, i_jma, correction_x, correction_y, correction_z):
    if processed:
        with open(path + '/Processed Data (Linear Acceleration).csv', 'r') as data_file:  # 解析a数据
            data = csv.reader(data_file, delimiter=',')
            for row in data:
                if row[0] == 'Time (s)':
                    continue
                raw_data_t.append(float(row[0]))
                ax.append(float(row[1]))
                ay.append(float(row[2]))
                az.append(float(row[3]))
                aa.append(float(row[4]))
        with open(path + '/Processed Data (Velocity).csv', 'r') as data_file:  # 解析v数据
            data = csv.reader(data_file, delimiter=',')
            for row in data:
                if row[0] == 'Time (s)':
                    continue
                vx.append(float(row[1]))
                vy.append(float(row[2]))
                vz.append(float(row[3]))
                va.append(float(row[4]))
    else:
        # 测定采样率
        if not sampling_rate:
            sampling_rate = ((len(raw_data_t) - 1) / raw_data_t[-1] - raw_data_t[0])
            print(f'您没有设置采样率，程序自动测定的采样率为：{sampling_rate} Hz\n----------')

        # 基线校正
        if auto_correction:
            if choice == '0':
                correction_x = sum(raw_data_x) / len(raw_data_x)
                correction_y = sum(raw_data_y) / len(raw_data_y)
                correction_z = sum(raw_data_z) / len(raw_data_z)
                print(f'自动基线校正结果：\nX方向：{correction_x}\nY方向：{correction_y}\nZ方向：{correction_z}\n----------')
                auto_correction = False
            else:
                print('数据分析模式下，自动基线校正不可用。\n----------')
        for x, y, z in zip(raw_data_x, raw_data_y, raw_data_z):
            x += correction_x
            y += correction_y
            z += correction_z
            corrected_ax.append(x)
            corrected_ay.append(y)
            corrected_az.append(z)

        # 转换为速度
        corrected_vx = (np.cumsum(corrected_ax)) * (1 / sampling_rate) + last_latest_vx
        corrected_vy = (np.cumsum(corrected_ay)) * (1 / sampling_rate) + last_latest_vy
        corrected_vz = (np.cumsum(corrected_az)) * (1 / sampling_rate) + last_latest_vz
        if choice == '0':
            last_latest_vx = corrected_vx[-1]
            last_latest_vy = corrected_vy[-1]
            last_latest_vz = corrected_vz[-1]

        # 对原三方向加速度和速度进行滤波
        # 加速度
        for row in filter_wave(x=corrected_ax):
            ax.append(row)
        for row in filter_wave(x=corrected_ay):
            ay.append(row)
        for row in filter_wave(x=corrected_az):
            az.append(row)
        # 速度
        for row in filter_wave(x=corrected_vx):
            vx.append(row)
        for row in filter_wave(x=corrected_vy):
            vy.append(row)
        for row in filter_wave(x=corrected_vz):
            vz.append(row)

        # 合成滤波后加速度
        # print('正在合成')
        for x, y, z in zip(ax, ay, az):
            aa.append(sqrt(x ** 2 + y ** 2 + z ** 2))
        # 速度
        for x, y, z in zip(vx, vy, vz):
            va.append(sqrt(x ** 2 + y ** 2 + z ** 2))

        if choice == '0':
            # 存储处理后数据
            save_processed_data(start_time, last_latest_time, (raw_data_t, ax, ay, az, aa), 'a')
            save_processed_data(start_time, last_latest_time, (raw_data_t, vx, vy, vz, va), 'v')

    # 计算PGA
    # print('正在筛选PGA')
    rt_a_max = max(aa)
    if rt_a_max > a_max:
        a_max = rt_a_max
        a_max_time = round(raw_data_t[aa.index(a_max)], 2)
    # 计算PGV
    rt_v_max = max(va)
    if rt_v_max > v_max:
        v_max = rt_v_max
        v_max_time = round(raw_data_t[va.index(v_max)], 2)

    # 计算烈度
    rt_ia_csis, rt_i_csis = csis_calc(rt_a_max, rt_v_max,csis_v)
    rt_ia_jma, rt_i_jma = jma_calc(rt_a_max)
    ia_csis = max(ia_csis, rt_ia_csis)
    i_csis = max(i_csis, rt_i_csis)
    ia_jma = max(ia_jma, rt_ia_jma)
    i_jma = max(i_jma, rt_i_jma)

    return sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, last_latest_time, a_max, v_max, ia_csis, i_csis, ia_jma, i_jma, rt_a_max, rt_v_max, rt_ia_csis, rt_i_csis, rt_ia_jma, rt_i_jma, a_max_time, v_max_time


if __name__ == '__main__':
    # 变量初始化
    raw_data_t = []  # 原时间数据序列
    raw_data_x = []  # 原x方向数据序列
    raw_data_y = []  # 原y方向数据序列
    raw_data_z = []  # 原z方向数据序列
    raw_data_a = []  # 原合成数据序列
    ia_csis, i_csis = 1.0, 1
    ia_jma, i_jma = -3.0, 0
    a_max = 0
    v_max = 0
    rt_a_max = 0
    rt_v_max = 0
    a_max_time = 0
    v_max_time = 0
    last_latest_time = 0
    is_recording = False
    config = get_config()
    ip = config['ip']
    delay = config['delay']
    retry_limit = config['retry_limit']
    refresh_time = config['refresh_time']
    sampling_rate = config['sampling_rate']
    csis_v = config['csis_v']
    jma_03 = config['jma_0.3']
    max_range = config['max_range']
    auto_correction = config['correction']['auto_correction']
    correction_x = config['correction']['x']
    correction_y = config['correction']['y']
    correction_z = config['correction']['z']
    last_latest_vx = 0
    last_latest_vy = 0
    last_latest_vz = 0

    init_folders()

    print('Phyphox Acceleration Analyser v2.1.0\nby HanZero\n')
    print('输入序号进入相应模式：\n0 - 实时监控\n1 - 数据分析\n')
    choice = input('>>> ')
    if choice == '0':
        # 请求IP
        if not ip:
            ip = input('----------\n请输入手机上显示的IP地址：')  # 格式化为http://192.168.xxx格式
        if ip[0] != 'h':
            ip = 'http://' + ip
        elif ip[4] == 's':
            ip = 'http://' + ip.removeprefix('https://')
        ip = ip.removesuffix('/')

        # 元数据获取
        start_time = get_meta(ip)

        # 开始实验
        print('----------')
        print(f'参数预览：\nIP地址：{ip}\n重试限制：{retry_limit}\n刷新间隔：{refresh_time} s\n采样率：{sampling_rate} Hz\n计算CSIS标准烈度时参考PGV：{csis_v}\n计算JMA标准烈度时使用持续最大0.3秒的PGA：{jma_03}\n“最近”最大PGA、PGV和烈度指代的时间长度：过去{max_range}次采样\n基线校正(x,y,z)：{correction_x},{correction_y},{correction_z}')
        print(f'实验将在{config["delay"]}秒后自动开始，您不需在app上设置启动延迟...')
        print('----------')
        sleep(config['delay'])
        try:
            get(ip+'/control?cmd=start')
        except Exception as e:
            throw_an_error(e, True)
        is_recording = True
        print(f'实验开始！')
        print('----------')

        # 主循环
        while is_recording:
            sleep(refresh_time)
            # 重置基线校正后和滤波后数据序列
            corrected_ax = []  # 基线校正后x方向加速度数据序列
            corrected_ay = []
            corrected_az = []
            ax = []  # 滤波后加速度x方向数据序列
            ay = []
            az = []
            aa = []
            vx = []  # 滤波后速度
            vy = []
            vz = []
            va = []
            #print(analyse_raw_data(start_time,0,ip))

            # 原始数据获取
            retry_count = 0
            rt_a_max, rt_ia_csis, rt_i_csis, rt_ia_jma, rt_i_jma = 0,0,0,0,0
            try:
                while True:  # 重试循环
                    try:
                        last_latest_time, raw_data_t, raw_data_x, raw_data_y, raw_data_z, raw_data_a, is_measuring = analyse_raw_data(start_time,last_latest_time,ip)
                        break  # 如果获取成功，跳出重试循环
                    except Exception as e:  # 如果获取失败
                        if retry_count >= config['retry_limit']:  # 如果重试次数达限，抛出异常
                            raise e
                        else:  # 否则进行下一次重试
                            retry_count += 1
                            print(f'原始数据获取失败，即将进行第{retry_count}次重试...\n----------')
                            continue
            except Exception as e:  # 捕获因重试次数达限抛出的异常，直接跳出大循环
                print(f'原始数据获取失败：{e}\n记录已终止。\n----------')
                #raise e
                break

            # 判断实验是否停止
            if not is_measuring:
                print('实验停止了？记录已终止。\n----------')
                break

            sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, last_latest_time, a_max, v_max, ia_csis, i_csis, ia_jma, i_jma, rt_a_max, rt_v_max, rt_ia_csis, rt_i_csis, rt_ia_jma, rt_i_jma, a_max_time, v_max_time = main_process(choice, False, sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, a_max, v_max, a_max_time, v_max_time, ia_csis, i_csis, ia_jma, i_jma, correction_x, correction_y, correction_z)

            # 结果输出
            print(strftime('/// %Y-%m-%d %H:%M:%S', gmtime()) + ' (UTC) ///')
            print(f'实时PGA：{round(rt_a_max,4)} m/s²')
            print(f'实时PGV：{round(rt_v_max,4)} m/s')
            print(f'实时烈度：\nCSIS: {rt_ia_csis} ({rt_i_csis})\nJMA: {rt_ia_jma} ({format_i_jma(rt_i_jma)})')
            print(f'本次记录最大PGA：{round(a_max,4)} m/s²（{a_max_time}s时刻）')
            print(f'本次记录最大PGV：{round(v_max,4)} m/s（{v_max_time}s时刻）')
            print(f'本次记录最大烈度：\nCSIS: {ia_csis} ({i_csis})\nJMA: {ia_jma} ({format_i_jma(i_jma)})')
            print('----------')
            # TODO: 完成-处理实验手动停止/连接断开时的应对方法（跳出循环开始统计）
            # TODO: 放弃-实时图象
            # TODO: 完成-终止后统计
            # TODO: 完成-又忘了做采样率自动分析了（以上2.17）
            # TODO: 完成-手动基线校正 未完成-自动
            # TODO: 完成-手动采样率设置 完成-自动
            # TODO: 完成-PGV转换

        print(f'实验数据已经存储至logs/{start_time}。您可以进入数据分析模式查看波形。\n----------')
    elif choice == '1':
        corrected_ax = []  # 基线校正后x方向加速度数据序列
        corrected_ay = []
        corrected_az = []
        ax = []  # 滤波后加速度x方向数据序列
        ay = []
        az = []
        aa = []
        vx = []  # 滤波后速度
        vy = []
        vz = []
        va = []

        path = input('----------\n请输入记录文件夹路径：').removeprefix('"').removesuffix('"').removesuffix('/').removesuffix(sep)

        try:
            open(path+'/Raw Data.csv', 'r')
        except FileNotFoundError as e:
            throw_an_error(f'文件不存在：{e}')

        try:
            open(path+'/Processed Data (Velocity).csv')
        except FileNotFoundError:
            print('----------\n这个文件夹中只有原始数据，因此将开始从头分析。\n----------')
            processed = False
        else:
            print('----------\n这个文件夹中有处理后的数据，因此将直接开始绘图。注意：基线校正已被禁用。\n----------')
            processed = True

        if not processed:
            with open(path+'/Raw Data.csv', 'r') as raw_data_file:  # 解析原数据
                raw_data = csv.reader(raw_data_file, delimiter=',')
                for row in raw_data:
                    if row[0] == 'Time (s)':
                        continue
                    raw_data_t.append(float(row[0]))
                    raw_data_x.append(float(row[1]))
                    raw_data_y.append(float(row[2]))
                    raw_data_z.append(float(row[3]))
                    raw_data_a.append(float(row[4]))

        sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, last_latest_time, a_max, v_max, ia_csis, i_csis, ia_jma, i_jma, rt_a_max, rt_v_max, rt_ia_csis, rt_i_csis, rt_ia_jma, rt_i_jma, a_max_time, v_max_time = main_process(choice, processed, sampling_rate, auto_correction, last_latest_vx, last_latest_vy, last_latest_vz, a_max, v_max, a_max_time, v_max_time, ia_csis, i_csis, ia_jma, i_jma, correction_x, correction_y, correction_z)

        # 打印结果
        print(strftime('/// %Y-%m-%d %H:%M:%S', gmtime()) + ' (UTC) 产出结果 ///')
        print(f'本次记录最大PGA：{a_max} m/s²（{a_max_time}s时刻）')
        print(f'本次记录最大PGV：{v_max} m/s（{v_max_time}s时刻）')
        print(f'本次记录最大烈度：\nCSIS: {ia_csis} ({i_csis})\nJMA: {ia_jma} ({format_i_jma(i_jma)})')
        print('----------')

        # 绘制图象
        # plt.plot(raw_data_t, data_x, linewidth=1, color='green')
        # plt.plot(raw_data_t, data_y, linewidth=1, color='blue')
        # plt.plot(raw_data_t, data_z, linewidth=1, color='yellow')
        fig, ((ax00, ax01), (ax10, ax11)) = plt.subplots(2, 2, sharex=True, sharey=True)
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False
        ax00.set_xlabel("时间 (s)")
        ax00.grid(True)
        ax00.set_ylabel("三分向合成后加速度 (m/s²)")
        ax00.plot(raw_data_t, aa, linewidth=1, color='blue')
        if a_max_time == v_max_time:
            ax00.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²\nPGV: {v_max}m/s)', (a_max_time, a_max))
        else:
            ax00.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²)', (a_max_time, a_max))
            ax00.annotate(f'({v_max_time}s\nPGV: {v_max}m/s)', (v_max_time, v_max))
        ax01.set_xlabel("时间 (s)")
        ax01.grid(True)
        ax01.set_ylabel("X方向加速度 (m/s²)")
        ax01.plot(raw_data_t, ax, linewidth=1, color='blue')
        if a_max_time == v_max_time:
            ax01.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²\nPGV: {v_max}m/s)', (a_max_time, a_max))
        else:
            ax01.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²)', (a_max_time, a_max))
            ax01.annotate(f'({v_max_time}s\nPGV: {v_max}m/s)', (v_max_time, v_max))
        ax10.set_xlabel("时间 (s)")
        ax10.grid(True)
        ax10.set_ylabel("Y方向加速度 (m/s²)")
        ax10.plot(raw_data_t, ay, linewidth=1, color='blue')
        if a_max_time == v_max_time:
            ax10.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²\nPGV: {v_max}m/s)', (a_max_time, a_max))
        else:
            ax10.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²)', (a_max_time, a_max))
            ax10.annotate(f'({v_max_time}s\nPGV: {v_max}m/s)', (v_max_time, v_max))
        ax11.set_xlabel("时间 (s)")
        ax11.grid(True)
        ax11.set_ylabel("Z方向加速度 (m/s²)")
        ax11.plot(raw_data_t, az, linewidth=1, color='blue')
        if a_max_time == v_max_time:
            ax11.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²\nPGV: {v_max}m/s)', (a_max_time, a_max))
        else:
            ax11.annotate(f'({a_max_time}s\nPGA: {a_max}m/s²)', (a_max_time, a_max))
            ax11.annotate(f'({v_max_time}s\nPGV: {v_max}m/s)', (v_max_time, v_max))

        plt.show()
    else:
        throw_an_error('无法识别您输入的序号！', True)

    input('按Enter退出...')
