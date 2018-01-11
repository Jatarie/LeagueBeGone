import requests
import re
from time import time, sleep
import os
import sys
import math
from cv2 import VideoCapture, imwrite, imread
import grequests
import numpy


imagedirectory = os.pardir + "\\images"
videodirectory = os.pardir + "\\videos"


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
        progress_string += "="
    for _ in range(remaining):
        progress_string += "|"
    progress_string += " ]"
    progress_string = "\r{} est: {}h {}m {:.0f}s [{}/{}]"\
        .format(progress_string, hour, minute, second, numerator, denominator)
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


def getChannelVodID(Channel):
    r = requests.get("https://api.twitch.tv/kraken/channels/"
                     "{}/videos?client_id=map2eprcvghxg8cdzdy2207giqnn64&broadcast_type=archive".format(Channel))
    data = r.json()
    return int(data["videos"][0]["url"][29:])


def getFirstFrameData(file, frame_counter):
    cap = VideoCapture(file)
    ret, frame = cap.read()
    imwrite("{}\\frame{}.jpg".format(imagedirectory, frame_counter), frame)
    img = imread("{}\\frame{}.jpg".format(imagedirectory, frame_counter))
    # os.remove("frame.jpg")
    if img is None:
        return None
    else:
        return img


def analyseFirstFrameOfVideoChunk(r, frame_number):
    with open(videodirectory + "\\chunk.mp4", "wb") as f:
        saveChunk(f, r)
    cap = VideoCapture(videodirectory + "\\chunk.mp4")
    ret, frame = cap.read()
    imwrite("frame{}.jpg".format(frame_number), frame)
    img = imread("frame{}.jpg".format( frame_number))
    os.remove("frame{}.jpg".format(frame_number))
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


def saveChunk(f, r):
    for chunk in r.iter_content(chunk_size=255):
        if chunk:
            f.write(chunk)


def downloadChunks(extension_list, source_link, filepath, filter_league, segment_length):
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
        downLink = (source_link[0] + extension_list[counter])
        r = requests.get(downLink)
        if filter_league:
            frame_number, league_present = analyseFirstFrameOfVideoChunk(r, frame_number)
            os.remove("chunk.mp4")
            frame_number += 1
        if league_present:
            counter += 20
            continue
        saveChunk(f, r)
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
    print("{:.2f} MB downladed in {:.2f} seconds at a rate of {:.2f} MB/s"
          .format(mbDownloaded, elapsedTime, (mbDownloaded / elapsedTime)))


def trimExtensionList(time_start, time_end, segment_length, extension_list):
    starting_index = int(int(time_start) / int(segment_length))
    if time_end == 0:
        ending_index = len(extension_list) - 1
    else:
        ending_index = int(int(time_end) / int(segment_length))
    return extension_list[starting_index:ending_index]


def analyseVod(segment_length, extension_list, low_link):
    sample_every_n_seconds = 300
    extensions_to_skip = int(sample_every_n_seconds / segment_length)
    sample_extention_list = extension_list[::extensions_to_skip]
    print(segment_length)
    print(extensions_to_skip)
    print(len(sample_extention_list))
    urls = [low_link[0] + sample_extention_list[i] for i in range(len(sample_extention_list))]
    rs = (grequests.get(u) for u in urls)
    responses = grequests.map(rs)
    frame_counter = 0
    for response in responses:
        frame_value = 0
        with open(videodirectory + "\\analysischunk.mp4", "wb") as f:
            saveChunk(f, response)
        img = getFirstFrameData(videodirectory + "\\analysischunk.mp4", frame_counter)
        for row in img:
            for pixel in row:
                frame_value += numpy.sum(pixel)
        os.rename("{}\\frame{}.jpg".format(imagedirectory, frame_counter), "{}\\{}.jpg".format(imagedirectory, frame_value))
        frame_counter += 1
    os.remove(videodirectory + "\\analysischunk.mp4")


def usherAPIRequest(token, sig, vodID):
    rawUsherAPIData = requests.get("http://usher.twitch.tv/vod/"
                                   "{}?nauthsig={}&nauth={}&allow_source=true".format(vodID, sig, token))
    m3u8links = re.findall(r'(http.+?m3u8)', rawUsherAPIData.text)
    source_m3u8link = m3u8links[0]
    low_m3u8link = m3u8links[len(m3u8links)-1]
    raw_m3u8link_data = requests.get(source_m3u8link)
    segment_length = int(re.findall(r'(?<=EXTINF:)[0-9]+', raw_m3u8link_data.text)[0])
    extension_list = (re.findall(r'\n([^#]+)\n', raw_m3u8link_data.text))

    source_m3u8linkm_link = re.findall(r'(.+?)(?=index)', source_m3u8link)
    low_m3u8link_link = re.findall(r'(.+?)(?=index)', low_m3u8link)
    return extension_list, segment_length, source_m3u8linkm_link, low_m3u8link_link


def twitchAPIRequest(vodID):
    client_id = "map2eprcvghxg8cdzdy2207giqnn64"
    rawTwitchAPIJsonData = requests.get("https://api.twitch.tv/api/vods/"
                                        "{}/access_token?&client_id={}".format(vodID, client_id))
    jsonData = rawTwitchAPIJsonData.json()
    token = jsonData["token"]
    sig = jsonData["sig"]
    return token, sig


def fileHandler(vodID, dir_path):
    try:
        os.mkdir(videodirectory)
    except FileExistsError:
        pass
    try:
        os.mkdir(imagedirectory)
    except FileExistsError:
        pass
    file_list = os.listdir(videodirectory)
    for file in file_list:
        os.remove(videodirectory + "\\" + file)
    file_list = os.listdir(imagedirectory)
    for file in file_list:
        if ".jpg" in file:
            os.remove(imagedirectory + "\\" + file)

    filepath = videodirectory + "\\" + str(vodID) + ".mp4"
    try:
        os.remove(filepath)
    except FileNotFoundError:
        pass
    return filepath


def timeParser(time_start, time_end):
    h_start, m_start, s_start = re.findall(r'[0-9]+(?=[a-zA-Z])', time_start)
    time_start = int(h_start)*3600 + int(m_start)*60 + int(s_start)

    h_end, m_end, s_end = re.findall(r'[0-9]+(?=[a-zA-Z])', time_end)
    time_end = int(h_end)*3600 + int(m_end)*60 + int(s_end)

    return time_start, time_end


def getVideoParams():
    debug = input("Debug?(y/n) ")
    if debug == "y":
        filter_league = False
        time_start = '0h4m23s'
        time_end = '1h4m23s'
        channel = "draskyl"
        debug_vodid = input("VodID?(y/n) ")
        if debug_vodid == "n":
            VodID = getChannelVodID(channel)
        else:
            VodID = int(input("Enter VodID: "))
        return VodID, channel, filter_league, time_start, time_end
    tmp_var = input("Enter Vod ID or Twitch channel: ")
    try:
        VodID = int(tmp_var)
        channel = None
    except ValueError:
        channel = tmp_var
        VodID = None
    filter_league = bool(input("Filter League? Enter 'True' or 'False': "))
    time_start = input("Enter start time: eg. '1h4m23s': ")
    time_end = input("Enter end time, eg. '1h4m23s', enter 0 to download to the end of the vod: ")
    return VodID, channel, filter_league, time_start, time_end


def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    vodID, Channel, filter_league, time_start, time_end = getVideoParams()
    time_start, time_end = timeParser(time_start, time_end)
    filepath = fileHandler(vodID, dir_path)
    token, sig = twitchAPIRequest(vodID)
    extension_list, segment_length, source_link, low_link = usherAPIRequest(token, sig, vodID)
    analyseVod(segment_length, extension_list, low_link)
    extension_list = trimExtensionList(time_start, time_end, segment_length, extension_list)
    downloadChunks(extension_list, source_link, filepath, filter_league, segment_length)
    if os.path.exists(videodirectory + "\\chunk.mp4"):
        os.remove(videodirectory + "\\chunk.mp4")


if __name__ == "__main__":
    main()
