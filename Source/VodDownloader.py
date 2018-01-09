import numpy
import requests
import re
from time import time, sleep
import os
import sys
import math
import win32gui
import win32con
from cv2 import VideoCapture, imwrite, imread


def twitchAPIRequest(vodID):
    start = time()
    rawTwitchAPIJsonData = requests.get("https://api.twitch.tv/api/vods/{}/access_token?&client_id=map2eprcvghxg8cdzdy2207giqnn64".format(vodID))
    # print("Twitch API call successful in {:.2f} seconds".format(time()-start))
    jsonData = rawTwitchAPIJsonData.json()
    token = jsonData["token"]
    sig = jsonData["sig"]
    return token, sig


def usherAPIRequest(token, sig, vodID, length_of_vid):
    start = time()
    rawUsherAPIData = requests.get("http://usher.twitch.tv/vod/{}?nauthsig={}&nauth={}&allow_source=true".format(vodID, sig, token))
    # print("Usher API call successful in {:.2f} seconds".format(time()-start))
    intermediate_m3u8link = re.findall(r'(http)(.+?)(m3u8)', rawUsherAPIData.text)[0]
    m3u8link = intermediate_m3u8link[0] + intermediate_m3u8link[1] + intermediate_m3u8link[2]
    raw_m3u8link_data = requests.get(m3u8link)
    if "muted" in m3u8link:
        m3u8link = re.findall(r'(.+?)(?=index)', m3u8link)[0]

    extension_list = (re.findall(r'\n([^#]+)\n', raw_m3u8link_data.text))
    # print("VOD length is {} seconds".format(len(extension_list)*6))
    start_of_link = re.findall(r'(.+)(chunked/)', m3u8link)
    start_of_link = start_of_link[0][0] + start_of_link[0][1]
    if length_of_vid == 0:
        return extension_list, start_of_link
    return extension_list[len(extension_list)-int(length_of_vid/6):], start_of_link


def fileHandler(vodID, dir_path):
    try:
        os.mkdir("vods")
    except FileExistsError:
        pass
    try:
        os.mkdir("images")
    except FileExistsError:
        pass
    file_list = os.listdir("vods")
    for file in file_list:
        os.remove("vods\\" + file)
    file_list = os.listdir(dir_path)
    for file in file_list:
        if ".jpg" in file:
            os.remove(file)

    filepath = "vods\\" + str(vodID) + ".mp4"
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass
    return filepath


def progressbar(numerator, denominator, time_remaining):
    hour = math.floor(time_remaining/3600)
    time_remaining -= hour * 3600
    minute = math.floor(time_remaining / 60)
    time_remaining -= minute * 60
    second = time_remaining
    fraction = numerator / denominator
    progress = round(20 * fraction)
    remaining = 20 - progress
    progress_string = "[ "
    for _ in range(progress):
        # progress_string += u"\u258D"
        progress_string += "="
    for _ in range(remaining):
        progress_string += "|"
        # progress_string += u"\u2009" * 2
    progress_string += " ]"
    progress_string = "\r{} est: {}h {}m {:.0f}s [{}/{}]".format(progress_string, hour, minute, second, numerator, denominator)
    sys.stdout.write(progress_string)
    sys.stdout.flush()


def timeremaining(start, extension_list, i):
    time_elapsed = time() - start
    chunks_completed = i
    if time_elapsed == 0 or chunks_completed == 0:
        return len(extension_list)
    chunks_remaining = len(extension_list) - i
    ave_chunk_completion_time = time_elapsed / chunks_completed
    return ave_chunk_completion_time * chunks_remaining


def downloadChunks(extension_list, start_of_link, filepath, filter_league):
    print("\nStarting download...")
    start = time()
    frame_number = 0
    league_present = False
    len_extension_list = len(extension_list)
    counter = 0
    f = open(filepath, "ab")
    file_open = False

    while len_extension_list > counter:
        time_remaining = timeremaining(start, extension_list, counter)
        progressbar(counter+1, len(extension_list), time_remaining)
        downLink = (start_of_link + extension_list[counter])
        r = requests.get(downLink)
        if filter_league:
            frame_number, league_present = analyseFirstFrameOfVideoChunk(r, frame_number)
            os.remove("chunk.mp4")
            frame_number += 1
        if league_present:
            counter += 20
            continue
        for chunk in r.iter_content(chunk_size=255):
            if chunk:
                f.write(chunk)
        if not file_open:
            os.startfile(filepath)
            file_open = True
        counter += 1

    sleep(0.1)
    sys.stdout.write("\rDownloaded completed\n")
    sys.stdout.flush()
    statinfo = os.stat(filepath)
    elapsedTime = time()-start
    mbDownloaded = statinfo.st_size / 1000000
    print("{:.2f} MB downladed in {:.2f} seconds at a rate of {:.2f} MB/s".format(mbDownloaded, elapsedTime, (mbDownloaded / elapsedTime)))


def getChannelVodID(Channel):
    r = requests.get("https://api.twitch.tv/kraken/channels/{}/videos?client_id=map2eprcvghxg8cdzdy2207giqnn64&broadcast_type=archive".format(Channel))
    data = r.json()
    return int(data["videos"][0]["url"][29:])


def windowFocus(hwnd, lParam):
    if win32gui.IsWindowVisible(hwnd):
        if "VLC" in win32gui.GetWindowText(hwnd):
            win32gui.MoveWindow(hwnd, 0, 0, 1920, 1080, True)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)


def analyseFirstFrameOfVideoChunk(r, frame_number):
    with open("chunk.mp4", "wb") as f:
        for chunk in r.iter_content(chunk_size=255):
            if chunk:
                f.write(chunk)
    cap = VideoCapture("chunk.mp4")
    ret, frame = cap.read()
    imwrite("images\\frame{}.jpg".format(frame_number), frame)
    img = imread("frame{}.jpg".format(frame_number))
    os.remove("images\\frame{}.jpg".format(frame_number))
    if img is None:
        return frame_number, False
    px1 = img[1056, 1893]
    px2 = img[1040, 1000]
    px3 = img[801, 1830]
    true_list = []
    if px1[0] < 10 and px1[1] < 10 and px1[2] < 10:
        true_list.append(True)
    if 50 > px2[0] > 15 and 40 > px2[1] > 20 and 40 > px2[2] > 10:
        true_list.append(True)
    if 70 > px3[0] > 40 and 110 > px3[1] > 80 and 130 > px3[2] > 90:
        true_list.append(True)
    if len(true_list) >= 2:
        # os.rename("frame{}.jpg".format(frame_number), "{}-LEAGUE-{}-{}-{}.jpg".format(frame_number, px1, px2, px3))
        return frame_number, True
    # os.rename("frame{}.jpg".format(frame_number), "{}-Normal-{}-{}-{}.jpg".format(frame_number, px1, px2, px3))
    return frame_number, False


def getVideoParams():
    VodID = int(input("Enter VodID: "))
    # VodID = 216537159
    filter_league = bool(input("Filter League? Enter 'True' or 'False': "))
    length_of_vid = 0
    channel = "destiny"
    return VodID, length_of_vid, channel, filter_league


def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    vodID, length_of_vid, Channel, filter_league = getVideoParams()
    if not vodID:
        vodID = getChannelVodID(Channel)
    filepath = fileHandler(vodID, dir_path)
    token, sig = twitchAPIRequest(vodID)
    extension_list, start_of_link = usherAPIRequest(token, sig, vodID, length_of_vid)
    downloadChunks(extension_list, start_of_link, filepath, filter_league)
    win32gui.EnumWindows(windowFocus, None)
    if os.path.exists("chunk.mp4"):
        os.remove("chunk.mp4")


if __name__ == "__main__":
    main()
