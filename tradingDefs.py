import json
import socket
import logging
import time
import ssl
from threading import Thread
import os
from datetime import datetime
from datetime import timedelta
from datetime import date
import datetime as datetimeTime
from pprint import pprint
import math
import requests
import eventlet
from copy import deepcopy
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import matplotlib.ticker as ticker
from dateutil.relativedelta import *
import six

sns.set_style('whitegrid')
os.chdir(os.path.dirname(__file__))

accountType = "demo"

# set to true on debug environment only
DEBUG = True
DEFAULT_XAPI_ADDRESS = 'xapi.xtb.com'
DEFUALT_XAPI_STREAMING_PORT = 5113

"""
# default connection properites
if accountType == "real":
    DEFAULT_XAPI_ADDRESS = 'xapi.xtb.com'
    DEFAULT_XAPI_PORT = 5112
    DEFUALT_XAPI_STREAMING_PORT = 5113
else:
    DEFAULT_XAPI_ADDRESS = 'xapi.xtb.com'
    DEFAULT_XAPI_PORT = 5124
    DEFUALT_XAPI_STREAMING_PORT = 5125
"""


# API inter-command timeout (in ms)
API_SEND_TIMEOUT = 1000

# max connection tries
API_MAX_CONN_TRIES = 100

# logger properties
logger = logging.getLogger("jsonSocket")
FORMAT = '[%(asctime)-15s][%(funcName)s:%(lineno)d] %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG,
                    filename='error_logs.log')

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


def reverse_dict(dictionary):
    reversed_keys = reversed(list(dictionary.keys()))
    return {key: dictionary[key]
            for key in reversed_keys
            }


def truncate(number, digits) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def renderDataFrameImage(data, col_width=3.0, row_height=0.625, font_size=14,
                         header_color='#40466e', row_colors=['#f1f1f2', 'w'], edge_color='w',
                         bbox=[0, 0, 1, 1], header_columns=0,
                         ax=None, **kwargs):
    if ax is None:
        size = (np.array(data.shape[::-1]) + np.array([0, 1])
                ) * np.array([col_width, row_height])
        fig, ax = plt.subplots(figsize=size)
        ax.axis('off')

    mpl_table = ax.table(cellText=data.values, bbox=bbox,
                         colLabels=data.columns, **kwargs)

    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(font_size)

    for k, cell in six.iteritems(mpl_table._cells):
        cell.set_edgecolor(edge_color)
        if k[0] == 0 or k[1] < header_columns:
            cell.set_text_props(weight='bold', color='w')
            cell.set_facecolor(header_color)
        else:
            cell.set_facecolor(row_colors[k[0] % len(row_colors)])
    return ax


class TransactionSide(object):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5


class TransactionType(object):
    ORDER_OPEN = 0
    ORDER_CLOSE = 2
    ORDER_MODIFY = 3
    ORDER_DELETE = 4


class JsonSocket(object):
    def __init__(self, address, port, encrypt=False):
        self._ssl = encrypt
        if self._ssl != True:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = ssl.wrap_socket(sock)
        self.conn = self.socket
        self._timeout = None
        self._address = address
        self._port = port
        self._decoder = json.JSONDecoder()
        self._receivedData = ''

    def connect(self):
        for _ in range(API_MAX_CONN_TRIES):
            try:
                self.socket.connect((self.address, self.port))
                self.socket.settimeout(6)
            except socket.error as msg:
                logger.error("SockThread Error: %s" % msg)
                time.sleep(1)
                continue
            # logger.info("Socket connected")
            return True
        return False

    def _sendObj(self, obj):
        msg = json.dumps(obj)
        self._waitingSend(msg)

    def _waitingSend(self, msg):
        if self.socket:
            sent = 0
            msg = msg.encode('utf-8')
            while sent < len(msg):
                sent += self.conn.send(msg[sent:])
                # logger.info('Sent: ' + str(msg))
                time.sleep(API_SEND_TIMEOUT/1000)

    def _read(self, bytesSize=4096):
        if not self.socket:
            raise RuntimeError("socket connection broken")
        while True:
            char = self.conn.recv(bytesSize).decode()
            self._receivedData += char
            try:
                (resp, size) = self._decoder.raw_decode(self._receivedData)
                if size == len(self._receivedData):
                    self._receivedData = ''
                    break
                elif size < len(self._receivedData):
                    self._receivedData = self._receivedData[size:].strip()
                    break
            except ValueError as e:
                continue
        # logger.info('Received: ' + str(resp))
        return resp

    def _readObj(self):
        msg = self._read()
        return msg

    def close(self):
        # logger.debug("Closing socket")
        self._closeSocket()
        if self.socket is not self.conn:
            # logger.debug("Closing connection socket")
            self._closeConnection()

    def _closeSocket(self):
        self.socket.close()

    def _closeConnection(self):
        self.conn.close()

    def _get_timeout(self):
        return self._timeout

    def _set_timeout(self, timeout):
        self._timeout = timeout
        self.socket.settimeout(timeout)

    def _get_address(self):
        return self._address

    def _set_address(self, address):
        pass

    def _get_port(self):
        return self._port

    def _set_port(self, port):
        pass

    def _get_encrypt(self):
        return self._ssl

    def _set_encrypt(self, encrypt):
        pass

    timeout = property(_get_timeout, _set_timeout,
                       doc='Get/set the socket timeout')
    address = property(_get_address, _set_address,
                       doc='read only property socket address')
    port = property(_get_port, _set_port, doc='read only property socket port')
    encrypt = property(_get_encrypt, _set_encrypt,
                       doc='read only property socket port')


class APIClient(JsonSocket):
    def __init__(self, accType, address=DEFAULT_XAPI_ADDRESS, encrypt=True):

        if accType == "real":
            port = 5112
        else:
            port = 5124

        super(APIClient, self).__init__(address, port, encrypt)
        if(not self.connect()):
            raise Exception("Cannot connect to " + address + ":" +
                            str(port) + " after " + str(API_MAX_CONN_TRIES) + " retries")

    def execute(self, dictionary):
        self._sendObj(dictionary)
        return self._readObj()

    def disconnect(self):
        self.close()

    def commandExecute(self, commandName, arguments=None):
        return self.execute(baseCommand(commandName, arguments))


class APIStreamClient(JsonSocket):
    def __init__(self, address=DEFAULT_XAPI_ADDRESS, port=DEFUALT_XAPI_STREAMING_PORT, encrypt=True, ssId=None,
                 tickFun=None, tradeFun=None, balanceFun=None, tradeStatusFun=None, profitFun=None, newsFun=None):
        super(APIStreamClient, self).__init__(address, port, encrypt)
        self._ssId = ssId

        self._tickFun = tickFun
        self._tradeFun = tradeFun
        self._balanceFun = balanceFun
        self._tradeStatusFun = tradeStatusFun
        self._profitFun = profitFun
        self._newsFun = newsFun

        if(not self.connect()):
            raise Exception("Cannot connect to streaming on " + address + ":" +
                            str(port) + " after " + str(API_MAX_CONN_TRIES) + " retries")

        self._running = True
        self._t = Thread(target=self._readStream, args=())
        self._t.setDaemon(True)
        self._t.start()

    def _readStream(self):
        while (self._running):
            msg = self._readObj()
            # logger.info("Stream received: " + str(msg))
            if (msg["command"] == 'tickPrices'):
                self._tickFun(msg)
            elif (msg["command"] == 'trade'):
                self._tradeFun(msg)
            elif (msg["command"] == "balance"):
                self._balanceFun(msg)
            elif (msg["command"] == "tradeStatus"):
                self._tradeStatusFun(msg)
            elif (msg["command"] == "profit"):
                self._profitFun(msg)
            elif (msg["command"] == "news"):
                self._newsFun(msg)

    def disconnect(self):
        self._running = False
        self._t.join()
        self.close()

    def execute(self, dictionary):
        self._sendObj(dictionary)

    def subscribePrice(self, symbol):
        self.execute(dict(command='getTickPrices',
                          symbol=symbol, streamSessionId=self._ssId))

    def subscribePrices(self, symbols):
        for symbolX in symbols:
            self.subscribePrice(symbolX)

    def subscribeTrades(self):
        self.execute(dict(command='getTrades', streamSessionId=self._ssId))

    def subscribeBalance(self):
        self.execute(dict(command='getBalance', streamSessionId=self._ssId))

    def subscribeTradeStatus(self):
        self.execute(dict(command='getTradeStatus',
                          streamSessionId=self._ssId))

    def subscribeProfits(self):
        self.execute(dict(command='getProfits', streamSessionId=self._ssId))

    def subscribeNews(self):
        self.execute(dict(command='getNews', streamSessionId=self._ssId))

    def unsubscribePrice(self, symbol):
        self.execute(dict(command='stopTickPrices',
                          symbol=symbol, streamSessionId=self._ssId))

    def unsubscribePrices(self, symbols):
        for symbolX in symbols:
            self.unsubscribePrice(symbolX)

    def unsubscribeTrades(self):
        self.execute(dict(command='stopTrades', streamSessionId=self._ssId))

    def unsubscribeBalance(self):
        self.execute(dict(command='stopBalance', streamSessionId=self._ssId))

    def unsubscribeTradeStatus(self):
        self.execute(dict(command='stopTradeStatus',
                          streamSessionId=self._ssId))

    def unsubscribeProfits(self):
        self.execute(dict(command='stopProfits', streamSessionId=self._ssId))

    def unsubscribeNews(self):
        self.execute(dict(command='stopNews', streamSessionId=self._ssId))


# Command templates
def baseCommand(commandName, arguments=None):
    if arguments == None:
        arguments = dict()
    return dict([('command', commandName), ('arguments', arguments)])


def loginCommand(userId, password, appName=''):
    return baseCommand('login', dict(userId=userId, password=password, appName=appName))


# example function for processing ticks from Streaming socket
def procTickExample(msg):
    print("TICK: ", msg)

# example function for processing trades from Streaming socket


def procTradeExample(msg):
    print("TRADE: ", msg)

# example function for processing trades from Streaming socket


def procBalanceExample(msg):
    print("BALANCE: ", msg)

# example function for processing trades from Streaming socket


def procTradeStatusExample(msg):
    print("TRADE STATUS: ", msg)

# example function for processing trades from Streaming socket


def procProfitExample(msg):
    print("PROFIT: ", msg)

# example function for processing news from Streaming socket


def procNewsExample(msg):
    print("NEWS: ", msg)

# ---------------------------------------------------------------------


def save_actual_calendar_json(client):
    calendarFromApi = client.commandExecute('getCalendar')

    argument = {
        "symbol": "EURPLN"
    }

    fullCalendar = []
    index = 0
    for entryDict in calendarFromApi["returnData"]:
        if entryDict["impact"] == "3" or entryDict["impact"] == "2":
            fullCalendar.append(entryDict)
            fullCalendar[index]["time"] = str(datetime.fromtimestamp(
                entryDict["time"] / 1000))
            index += 1

    with open("fullCalendar.json", "w", encoding="UTF-8-sig") as fileJson:
        json.dump(fullCalendar, fileJson, ensure_ascii=False, indent=4)


def get_important_calendar_events_dict(client, importantCountriesList):
    calendarFromApi = client.commandExecute('getCalendar')

    fullCalendar = []
    index = 0
    for entryDict in calendarFromApi["returnData"]:
        if (entryDict["country"] in importantCountriesList) and (entryDict["impact"] == "3" or entryDict["impact"] == "2"):
            fullCalendar.append(entryDict)
            fullCalendar[index]["time"] = str(datetime.fromtimestamp(
                entryDict["time"] / 1000))
            index += 1
    return fullCalendar


class Calendar:

    def __init__(self, client, importantCurrencies):

        self.importantCurrencies = importantCurrencies

        self.fullOnlyImportantCalendar = Calendar.get_important_calendar_events_dict(
            self, client)

        onlyAnnouncementsTimes = [event["time"].split(" ")[1]
                                  for event in self.fullOnlyImportantCalendar
                                  ]

        self.onlyAnnouncementsTimesSorted = sorted(
            list(set(onlyAnnouncementsTimes)), reverse=True)

        self.currentTitlesDict = {event["title"]: ""
                                  for event in self.fullOnlyImportantCalendar
                                  }

    def get_important_calendar_events_dict(self, client):
        calendarFromApi = client.commandExecute('getCalendar')

        with open("countriesCurrencies.json", "r", encoding="UTF-8-sig") as countriesCurrencies:
            countriesCurrencies = json.load(countriesCurrencies)

        importantCountriesList = [country
                                  for country in countriesCurrencies
                                  if countriesCurrencies[country] in self.importantCurrencies
                                  ]
        # get today and tommorow timestamps

        timeDiff = timedelta(hours=3)
        startTime = (
            datetime.now() - timeDiff).strftime("%Y-%m-%d %H:%M:%S")

        # tymczasowo, żeby cokolwiek było w kalendarzu
        # startTime = str(datetime.today().date()) + " 00:00:00"
        dateDiff = timedelta(days=1)
        endTime = str((datetime.now() + dateDiff).date()) + " 23:59:59"

        self.startDateTimestamp = int(datetime.timestamp(
            datetime.strptime(startTime, '%Y-%m-%d %H:%M:%S')))*1000
        self.endDateTimestamp = int(datetime.timestamp(
            datetime.strptime(endTime, '%Y-%m-%d %H:%M:%S')))*1000
        # get only important events from today calendar
        fullCalendar = []
        index = 0
        for entryDict in calendarFromApi["returnData"]:
            if (entryDict["country"] in importantCountriesList) and \
                (entryDict["time"] >= self.startDateTimestamp) and \
                    (entryDict["time"] < self.endDateTimestamp) and \
                    (entryDict["impact"] == "3" or entryDict["impact"] == "2"):
                fullCalendar.append(entryDict)
                fullCalendar[index]["time"] = str(datetime.fromtimestamp(
                    entryDict["time"] / 1000))
                index += 1
            if entryDict["forecast"] == "":
                entryDict["forecast"] = entryDict["previous"]

        return fullCalendar

    def save_actual_calendar_json(self):

        with open("fullCalendar2.json", "w", encoding="UTF-8-sig") as fileJson:
            json.dump(self.fullOnlyImportantCalendar,
                      fileJson, ensure_ascii=False, indent=4)


class FileSupport:

    @staticmethod
    def read_file(name, support=False):
        if support == True:
            path_parent = os.path.dirname(os.getcwd())
            os.chdir(path_parent)
            with open(name + ".json", "r", encoding="UTF-8-sig") as jsonFile:
                os.chdir(os.path.dirname(__file__))
                return json.load(jsonFile)
        else:
            with open(name + ".json", "r", encoding="UTF-8-sig") as jsonFile:
                return json.load(jsonFile)

    @staticmethod
    def save_file(name, dictionary, directory=""):

        with open(directory + name + ".json", "w", encoding="UTF-8-sig") as jsonFile:
            json.dump(dictionary, jsonFile, ensure_ascii=False, indent=4)


class BullsAndBears:

    def __init__(self, calendarFromApi):

        self.importantWithCurrentValue = [event
                                          for event in calendarFromApi.fullOnlyImportantCalendar
                                          if event["current"] != ""
                                          ]

        titlesDictionaryDirections = FileSupport.read_file(
            "titlesDictionaryDirections")
        # check for new titles
        newTitlesDict = {title: "Update Needed"
                         for title in calendarFromApi.currentTitlesDict
                         if title not in titlesDictionaryDirections
                         }
        FileSupport.save_file("newTitles", newTitlesDict)

        # merge new titles with older file, save json
        updatedTitlesDirections = {
            **titlesDictionaryDirections, **newTitlesDict}
        FileSupport.save_file("titlesDictionaryDirections",
                              updatedTitlesDirections)
        titlesDictionaryDirections = updatedTitlesDirections

        countriesCurrencies = FileSupport.read_file("countriesCurrencies")

        self.bullsCurrencies = [countriesCurrencies[eventWithCurrent["country"]]
                                for eventWithCurrent in self.importantWithCurrentValue
                                if (titlesDictionaryDirections[eventWithCurrent["title"]] == "Better Up" and
                                    (float(eventWithCurrent["current"]) - BullsAndBears.change_to_zeros(self, eventWithCurrent["forecast"]) > 0)) or
                                (titlesDictionaryDirections[eventWithCurrent["title"]] == "Better Down" and
                                 (float(eventWithCurrent["current"]) - BullsAndBears.change_to_zeros(self, eventWithCurrent["forecast"]) < 0)) or
                                BullsAndBears.check_minimum_value_bull(
            self, eventWithCurrent["title"], eventWithCurrent["current"])

        ]

        self.bearsCurrencies = [countriesCurrencies[eventWithCurrent["country"]]
                                for eventWithCurrent in self.importantWithCurrentValue
                                if (titlesDictionaryDirections[eventWithCurrent["title"]] == "Better Up" and
                                    (float(eventWithCurrent["current"]) - BullsAndBears.change_to_zeros(self, eventWithCurrent["forecast"]) < 0)) or
                                (titlesDictionaryDirections[eventWithCurrent["title"]] == "Better Down" and
                                 (float(eventWithCurrent["current"]) - BullsAndBears.change_to_zeros(self, eventWithCurrent["forecast"]) > 0)) or
                                BullsAndBears.check_minimum_value_bear(
            self, eventWithCurrent["title"], eventWithCurrent["current"])

        ]

        self.bearCurrenciesUnique = [currency
                                     for currency in list(set(self.bearsCurrencies))
                                     if currency not in list(set(self.bullsCurrencies))
                                     ]

        self.bullCurrenciesUnique = [currency
                                     for currency in list(set(self.bullsCurrencies))
                                     if currency not in list(set(self.bearsCurrencies))
                                     ]

    @staticmethod
    def change_trades_order(semiTrades, fullTrades, withoutCurrent):

        finalOrderTrades = {}
        orderAfterSemi = {}
        orderAfterFull = {}

        if len(list(semiTrades.keys())) > 0:
            for pair in reverse_dict(semiTrades):
                if pair in withoutCurrent:
                    orderAfterSemi[pair] = withoutCurrent[pair]

        if len(list(fullTrades.keys())) > 0:
            for pair in reverse_dict(fullTrades):
                if pair in withoutCurrent:
                    orderAfterFull[pair] = withoutCurrent[pair]

        finalOrderTrades = {**orderAfterFull, **orderAfterSemi}

        for pair in withoutCurrent:
            if pair not in finalOrderTrades:
                finalOrderTrades[pair] = withoutCurrent[pair]

        return finalOrderTrades

    def change_to_zeros(self, string):
        if string == "":
            return 0
        else:
            return float(string)

    def check_minimum_value_bull(self, key, comparedValue):
        with open("titlesDictionaryMinimums.json", "r", encoding="UTF-8-sig") as jsonFile:
            titlesDictionaryMinimums = json.load(jsonFile)

        try:
            if float(titlesDictionaryMinimums[key]) < float(comparedValue):
                return True
        except:
            return False

    def check_minimum_value_bear(self, key, comparedValue):
        with open("titlesDictionaryMinimums.json", "r", encoding="UTF-8-sig") as jsonFile:
            titlesDictionaryMinimums = json.load(jsonFile)

        try:
            if float(titlesDictionaryMinimums[key]) > float(comparedValue):
                return True
        except:
            return False

    def get_possible_trades_both_lists(self, possibleCurrencyPairs):

        allCombinations = []
        listToMakeCombinations = self.bearCurrenciesUnique + \
            self.bullCurrenciesUnique

        for currency in listToMakeCombinations:
            for currencyIndex in range(len(listToMakeCombinations)):
                currentCombination = str(currency) + \
                    str(listToMakeCombinations[currencyIndex])
                if currentCombination in possibleCurrencyPairs:
                    allCombinations.append(currentCombination)
        possibleFullTrades = list(set(allCombinations))

        # nadanie kierunku trejdom na podstawie kalendarza
        return BullsAndBears.get_trade_directions_for_pairs(self, possibleFullTrades)

    def get_semi_possible_trades(self, possibleCurrencyPairs, importantCurrencies):
        allCombinations = []
        listToMakeCombinations = self.bearCurrenciesUnique + \
            self.bullCurrenciesUnique

        for possibleCurrency in listToMakeCombinations:
            for currency in importantCurrencies:
                currentCombination = str(possibleCurrency) + str(currency)
                if (currentCombination in possibleCurrencyPairs) and (possibleCurrency in currentCombination):
                    allCombinations.append(currentCombination)
                alternativeCombination = str(currency) + str(possibleCurrency)
                if (alternativeCombination in possibleCurrencyPairs) and (possibleCurrency in alternativeCombination):
                    allCombinations.append(alternativeCombination)
        possibleSemiTrades = list(set(allCombinations))

        # nadanie kierunku trejdom na podstawie kalendarza
        return BullsAndBears.get_trade_directions_for_pairs(self, possibleSemiTrades)

    @staticmethod
    def get_possible_pairs_from_currencies_list(currenciesList, possibleCurrencyPairs, importantCurrencies):
        allCombinations = []
        listToMakeCombinations = currenciesList

        for possibleCurrency in listToMakeCombinations:
            for currency in importantCurrencies:
                currentCombination = str(possibleCurrency) + str(currency)
                if (currentCombination in possibleCurrencyPairs) and (possibleCurrency in currentCombination):
                    allCombinations.append(currentCombination)
                alternativeCombination = str(currency) + str(possibleCurrency)
                if (alternativeCombination in possibleCurrencyPairs) and (possibleCurrency in alternativeCombination):
                    allCombinations.append(alternativeCombination)
        uniquePairs = []
        for pair in allCombinations:
            if pair not in uniquePairs:
                uniquePairs.append(pair)
        return uniquePairs

    def get_unique_currency_pairs(self, pairsList):

        if len(list(pairsList.keys())) > 1:

            firstCurrenciesFromPairs = []
            secondCurrenciesFromPairs = []
            finalPairs = {}
            for pair in pairsList:
                firstCurrenciesFromPairs.append(pair[0:3])
                secondCurrenciesFromPairs.append(pair[3:6])
                allCurencies = firstCurrenciesFromPairs + secondCurrenciesFromPairs

                matchesDict = dict(Counter(allCurencies))

                if max(list(matchesDict.values())) < 2:
                    finalPairs[pair] = pairsList[pair]
                else:
                    firstCurrenciesFromPairs.pop()
                    secondCurrenciesFromPairs.pop()
                    allCurencies = firstCurrenciesFromPairs + secondCurrenciesFromPairs

            return finalPairs
        else:
            return pairsList

    def get_trade_directions_for_pairs(self, pairsList):

        if self.bullCurrenciesUnique == [] and \
                self.bearCurrenciesUnique == []:

            bothDict = {pair: "both"
                        for pair in pairsList
                        }
            return bothDict

        else:
            # sprawdzenie listy bull
            bullDict = {}
            for pair in pairsList:
                for bullCurrency in self.bullCurrenciesUnique:
                    if pair[3:6] in self.bullCurrenciesUnique and \
                            pair[0:3] in self.bullCurrenciesUnique:
                        pass
                    elif pair[3:6] == bullCurrency:
                        bullDict[pair] = "sell"
                    elif pair[0:3] == bullCurrency:
                        bullDict[pair] = "buy"
                    elif pair[3:6] not in self.bearCurrenciesUnique and \
                            pair[0:3] not in self.bearCurrenciesUnique and \
                            pair[3:6] not in self.bullCurrenciesUnique and \
                            pair[0:3] not in self.bullCurrenciesUnique:
                        bullDict[pair] = "both"

            # sprawdzenie listy bear
            bearDict = {}
            for pair in pairsList:
                for bearCurrency in self.bearCurrenciesUnique:
                    if pair[3:6] in self.bearCurrenciesUnique and \
                            pair[0:3] in self.bearCurrenciesUnique:
                        pass
                    elif pair[3:6] == bearCurrency:
                        bearDict[pair] = "buy"
                    elif pair[0:3] == bearCurrency:
                        bearDict[pair] = "sell"
                    elif pair[3:6] not in self.bearCurrenciesUnique and \
                            pair[0:3] not in self.bearCurrenciesUnique and \
                            pair[3:6] not in self.bullCurrenciesUnique and \
                            pair[0:3] not in self.bullCurrenciesUnique:
                        bearDict[pair] = "both"

            return {**bullDict, **bearDict}

    @staticmethod
    def split_pairs_to_currencies(pairsList):
        firstCurrenciesFromPairs = [pair[0:3]
                                    for pair in pairsList
                                    ]

        secondCurrenciesFromPairs = [pair[3:6]
                                     for pair in pairsList
                                     ]
        allCurrencies = list(firstCurrenciesFromPairs +
                             secondCurrenciesFromPairs)
        uniqueCurrencies = []
        for currency in allCurrencies:
            if currency not in uniqueCurrencies:
                uniqueCurrencies.append(currency)
        return uniqueCurrencies


class Chart:

    def __init__(self, client, pair, timeFrame, startTime=None):
        timeFrames = {"day": 1440, "fourhour": 240,
                      "hour": 60, "halfhour": 30, "quater": 15, "five": 5, "one": 1}
        chosenTimeFrame = timeFrames[timeFrame]

        if startTime == None:
            timeDiff = timedelta(days=19)
            startTimeChart = str(
                datetime.today().date() - timeDiff) + " 00:00:00"
        else:
            startTimeChart = startTime

        # daty start w formacie timestamp
        startDateTimestampChart = int(datetime.timestamp(
            datetime.strptime(startTimeChart, '%Y-%m-%d %H:%M:%S')))*1000

        chart_info = {
            "start": startDateTimestampChart,
            "period": chosenTimeFrame,
            "symbol": pair,
            "ticks": 0
        }
        argument = {
            "info": chart_info
        }

        chartListDays = client.commandExecute(
            "getChartLastRequest", argument)["returnData"]["rateInfos"]

        numberOfDigits = {"EURUSD": 5, "USDJPY": 3, "GBPUSD": 5, "AUDUSD": 5,
                          "USDCAD": 5, "EURJPY": 3, "EURGBP": 5, "GBPJPY": 3,
                          "AUDJPY": 3, "AUDCAD": 5, "CADJPY": 3, "USDCHF": 5}

        for note in chartListDays:
            note["high"] = (float(note["open"]) +
                            float(note["high"])) / 10 ** numberOfDigits[pair]
            note["low"] = (float(note["open"]) +
                           float(note["low"])) / 10 ** numberOfDigits[pair]
            note["close"] = (float(note["open"]) +
                             float(note["close"])) / 10 ** numberOfDigits[pair]
            note["open"] = float(note["open"]) / 10 ** numberOfDigits[pair]
        time.sleep(0.1)
        self.chartReady = chartListDays


class SupportResistanceALL:

    def __init__(self):

        supportResistanceBIG = FileSupport.read_file(
            "SupportResistanceBIG", support=True)
        supportResistanceCURRENT = FileSupport.read_file(
            "SupportResistanceCURRENT", support=True)

        supportResistanceALL = {}
        for pair in supportResistanceBIG:
            supportResistanceALL[pair] = supportResistanceBIG[pair] + \
                supportResistanceCURRENT[pair]

        self.supportResistanceALL = supportResistanceALL
        self.supportResistanceBIG = supportResistanceBIG
        self.supportResistanceCURRENT = supportResistanceCURRENT


class Resistance:

    def __init__(self, client, pair, timeFrame, startTime=None):
        daysOfWeek = {0: "mon", 1: "tue", 2: "wed",
                      3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        chart = Chart(client, pair, timeFrame, startTime=startTime)

        if startTime == None:
            chartListDays = chart.chartReady
        else:
            chartListDays = chart.chartReady  # [:-1]

        for note in chartListDays:
            note["ctm"] = daysOfWeek[datetime.fromtimestamp(
                note["ctm"] / 1000).weekday()]

        amountOfWeeks = 3
        allCloses = []
        currentCloses = []
        mondayNo = 0
        if startTime == None:
            for note in list(reversed(chartListDays)):
                currentCloses.append(note["close"])
                if note["ctm"] == "sun":
                    mondayNo += 1
                    allCloses.append(max(currentCloses))
                    currentCloses = []
                if mondayNo == amountOfWeeks:
                    break
        else:
            for note in list(reversed(chartListDays)):
                currentCloses.append(note["close"])
            allCloses = max(currentCloses)

        self.allCloses = allCloses


class Support:

    def __init__(self, client, pair, timeFrame, startTime=None):
        daysOfWeek = {0: "mon", 1: "tue", 2: "wed",
                      3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        chart = Chart(client, pair, timeFrame, startTime=startTime)

        if startTime == None:
            chartListDays = chart.chartReady
        else:
            chartListDays = chart.chartReady  # [:-1]

        for note in chartListDays:
            note["ctm"] = daysOfWeek[datetime.fromtimestamp(
                note["ctm"] / 1000).weekday()]
        amountOfWeeks = 3
        supports = []
        resistances = []

        currentCloses = []
        mondayNo = 0

        if startTime == None:
            for note in list(reversed(chartListDays)):
                currentCloses.append(note["close"])
                if note["ctm"] == "sun":
                    mondayNo += 1
                    supports.append(min(currentCloses))
                    resistances.append(max(currentCloses))
                    currentCloses = []
                if mondayNo == amountOfWeeks:
                    break
        else:
            for note in list(reversed(chartListDays)):
                currentCloses.append(note["close"])
            supports = min(currentCloses)
            resistances = max(currentCloses)

        self.supports = supports
        self.resistances = resistances
        self.chartOneHour = chartListDays


class TradeProximity:

    def __init__(self, client, supportResistanceALL,  possibleTradesFromStoch, supportResistanceZoneSize, possibleCurrencyPairs=False, isJPYinPair=False):

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        self.supportResistanceALLRanges = {pair: [np.arange(price - (pipValue * supportResistanceZoneSize / 2), price + pipValue / 10 + (pipValue * supportResistanceZoneSize / 2), pipValue / 10).round(5)
                                                  for price in supportResistanceALL[pair]
                                                  ]
                                           for pair in supportResistanceALL
                                           }

        # sprawdz czy cena jest w strefie +- 4pips od oporu
        tradesWithOkProximityAndStoch = {}

        bidAsk = BidAsk(client, possibleCurrencyPairs)

        for pair in possibleCurrencyPairs:

            splittedPair = pair.split()[0]

            if TradeProximity.check_arange_arrays(self, bidAsk.bidPrices[splittedPair],  splittedPair):
                try:
                    tradesWithOkProximityAndStoch[splittedPair] = possibleTradesFromStoch[splittedPair]
                except:
                    pass
                self.priceInZone = True
            else:
                self.priceInZone = False

        self.tradesWithOkProximityAndStoch = tradesWithOkProximityAndStoch

    def check_arange_arrays(self, currentPrice,  pair):

        for array in self.supportResistanceALLRanges[pair]:
            if currentPrice in array:
                return True


class CandleRange:

    def __init__(self, client, timeFrame,  tradedPair, today=None, isJPYinPair=False):
        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        if today == "sun" or (today == "mon" and str(datetime.now().strftime("%H%M")) <= "0500"):
            if timeFrame == "hour":
                timeDiff = timedelta(hours=248)

        else:
            if timeFrame == "hour":
                timeDiff = timedelta(hours=169)

        startTimeChart = (
            datetime.now() - timeDiff).strftime("%Y-%m-%d %H:%M:%S")
        chart = Chart(client, tradedPair, timeFrame,
                      startTime=startTimeChart)

        chartListDays = chart.chartReady
        self.chartCandleRange = chartListDays

        candleRanges = [math.fabs(note["high"] - note["low"])
                        for note in chartListDays
                        ]

        # maxRange = round(max(candleRanges) / pipValue, 1)
        # minRange = round(min(candleRanges) / pipValue, 1)
        # print("maxRange", maxRange)
        # print("minRange", minRange)

        # self.averageMinMaxRange = round((maxRange + minRange) / 2, 0)

        self.averageCandleRange = round(
            get_average(candleRanges) / pipValue, 0)

        self.averageImpulsRange = round(self.averageCandleRange * 1.25, 0)

        self.lastCandleRange = round((
            chartListDays[-1]["high"] - chartListDays[-1]["low"]) / pipValue, 5)

        self.lastCandleTrueRange = math.fabs(round((
            chartListDays[-1]["open"] - chartListDays[-1]["close"]) / pipValue, 5))

        if chartListDays[-1]["open"] < chartListDays[-1]["close"]:
            self.candleDirection = "up"
        else:
            self.candleDirection = "down"


class SlowStoch:

    def __init__(self, client, possibleTradesDict, timeFrame, chart=None, today=None, isJPYinPair=False):

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        possibleTradesSlowStoch = {}
        self.averageHighLowsPerPair = {}

        for pair in possibleTradesDict:
            if chart == None:
                if today == "sun" or (today == "mon" and str(datetime.now().strftime("%H%M")) <= "0500"):
                    if timeFrame == "one":
                        timeDiff = timedelta(hours=73)
                    elif timeFrame == "five":
                        timeDiff = timedelta(hours=73)

                    elif timeFrame == "quater":
                        timeDiff = timedelta(hours=74)
                    elif timeFrame == "hour":
                        timeDiff = timedelta(hours=79)
                    elif timeFrame == "day":
                        timeDiff = timedelta(hours=192)

                else:
                    if timeFrame == "one":
                        timeDiff = timedelta(hours=0.6)
                    elif timeFrame == "five":
                        timeDiff = timedelta(hours=0.6)

                    elif timeFrame == "quater":
                        timeDiff = timedelta(hours=1.75)
                    elif timeFrame == "hour":
                        timeDiff = timedelta(hours=7)
                    elif timeFrame == "day":
                        timeDiff = timedelta(hours=192)

                startTimeChart = (
                    datetime.now() - timeDiff).strftime("%Y-%m-%d %H:%M:%S")
                chart = Chart(client, pair, timeFrame,
                              startTime=startTimeChart)

                # time.sleep(1)

                chartListDays = chart.chartReady

            else:
                chartListDays = chart

            # slow stoch
            if timeFrame == "one":
                k = 25  # z ilu ma dni być liczony stoch
                ps = 15  # zwalnianie stocha
            else:
                k = 5  # z ilu ma dni być liczony stoch
                ps = 5  # zwalnianie stocha

            currentK = 0

            lowsSlow = []
            highsSlow = []
            closeSlow = []

            if timeFrame == "hour":
                self.lastCandleRange = round((
                    chartListDays[-1]["high"] - chartListDays[-1]["low"]) / pipValue, 5)

                self.lastCandleTrueRange = math.fabs(round((
                    chartListDays[-1]["open"] - chartListDays[-1]["close"]) / pipValue, 5))

            for note in list(reversed(chartListDays)):
                lowsSlow.append(note["low"])
                highsSlow.append(note["high"])
                closeSlow.append(note["close"])

                currentK += 1
                if currentK == k + ps - 1:
                    break

            stochUp = []
            stochDown = []
            index = 0
            for index in range(ps):
                stochUp.append(
                    100 * (closeSlow[index] - min(lowsSlow[index: index + ps])))
                stochDown.append(
                    max(highsSlow[index: index + ps]) - min(lowsSlow[index: index + ps]))

            possibleTradesSlowStoch[pair] = round(
                sum(stochUp) / sum(stochDown), 2)

        self.possibleTradesSlowStoch = possibleTradesSlowStoch

    @staticmethod
    def get_possible_trades_from_stoch(possibleCurrencyPairs,  daySS, oneHourSS,  quaterSS, fiveSS, oneSS,
                                       buyM1, buyM5, buyM15, buyH1, buyD1,
                                       sellM1, sellM5, sellM15, sellH1, sellD1,
                                       possibleTradesFromADX, ADXvalue, minusDMI, plusDMI, strongTrendLevel, veryStrongTrendLevel):

        adjustedStochLimits = {}
        for pair in possibleCurrencyPairs:
            if possibleTradesFromADX[pair] == "buy":
                if plusDMI[pair] > minusDMI[pair] + 10 and (ADXvalue[pair] > veryStrongTrendLevel and plusDMI[pair] > veryStrongTrendLevel):
                    buyM1 += 2.5
                    buyM5 += 5
                    buyM15 += 5
                    buyH1 += 5
                elif plusDMI[pair] > minusDMI[pair] + 5 and (ADXvalue[pair] > strongTrendLevel and plusDMI[pair] > strongTrendLevel):
                    buyM5 += 2.5
                    buyM15 += 2.5
                    buyH1 += 2.5
            elif possibleTradesFromADX[pair] == "sell":
                if minusDMI[pair] > plusDMI[pair] + 10 and (ADXvalue[pair] > veryStrongTrendLevel and minusDMI[pair] > veryStrongTrendLevel):
                    sellM1 -= 2.5
                    sellM5 -= 5
                    sellM15 -= 5
                    sellH1 -= 5
                elif minusDMI[pair] > plusDMI[pair] + 5 and (ADXvalue[pair] > strongTrendLevel and minusDMI[pair] > strongTrendLevel):
                    sellM5 -= 2.5
                    sellM15 -= 2.5
                    sellH1 -= 2.5
            adjustedStochLimits[pair] = {"buyM1": buyM1, "buyM5": buyM5, "buyM15": buyM15, "buyH1": buyH1, "buyD1": buyD1,
                                         "sellM1": sellM1, "sellM5": sellM5, "sellM15": sellM15, "sellH1": sellH1, "sellD1": sellD1}

        possibleBuysStoch = {pair: "buy"
                             for pair in possibleCurrencyPairs
                             if oneSS[pair] <= adjustedStochLimits[pair]["buyM1"] and
                             fiveSS[pair] <= adjustedStochLimits[pair]["buyM5"] and
                             quaterSS[pair] <= adjustedStochLimits[pair]["buyM15"] and
                             oneHourSS[pair] <= adjustedStochLimits[pair]["buyH1"] and
                             daySS[pair] <= adjustedStochLimits[pair]["buyD1"]
                             }

        possibleSellsStoch = {pair: "sell"
                              for pair in possibleCurrencyPairs
                              if oneSS[pair] >= adjustedStochLimits[pair]["sellM1"] and
                              fiveSS[pair] >= adjustedStochLimits[pair]["sellM5"] and
                              quaterSS[pair] >= adjustedStochLimits[pair]["sellM15"] and
                              oneHourSS[pair] >= adjustedStochLimits[pair]["sellH1"] and
                              daySS[pair] >= adjustedStochLimits[pair]["sellD1"]
                              }

        return {**possibleBuysStoch, **possibleSellsStoch}


class MoneyManagement:

    def __init__(self, client):

        accountData = client.commandExecute("getMarginLevel")["returnData"]

        self.balance = accountData["balance"]
        self.margin = accountData["margin"]
        self.equity = accountData["equity"]
        self.marginFree = accountData["margin_free"]
        self.marginLevel = accountData["margin_level"]

    def count_volumes(self, resistanceDict, supportDict, possibleTradesWithAllOk):
        pass


class CurrentTrades:

    def __init__(self, client):

        tradesDirections = {0: "buy", 1: "sell"}

        arguments = {
            "openedOnly": True
        }

        self.openedTradesFullInfo = client.commandExecute(
            "getTrades", arguments)["returnData"]

        count = 0
        symbols = []
        for trade in self.openedTradesFullInfo:

            if trade["symbol"] in symbols:
                count += 1
                trade["symbol"] = str(trade["symbol"] + " " + str(count))
            symbols.append(trade["symbol"])

        self.openedTradesOnlyPairs = {trade["symbol"]: tradesDirections[trade["cmd"]]
                                      for trade in self.openedTradesFullInfo
                                      }

        self.openedTradesOpeningPrices = {trade["symbol"]: trade["open_price"]
                                          for trade in self.openedTradesFullInfo
                                          }
        self.openedTradesVolumes = {trade["symbol"]: trade["volume"]
                                    for trade in self.openedTradesFullInfo
                                    }
        self.openedTradesOrdersNo = {trade["symbol"]: trade["order"]
                                     for trade in self.openedTradesFullInfo
                                     }
        self.openedTradesStopLoss = {trade["symbol"]: trade["sl"]
                                     for trade in self.openedTradesFullInfo
                                     }
        self.openedTradesTakeProfit = {trade["symbol"]: trade["tp"]
                                       for trade in self.openedTradesFullInfo
                                       }
        self.openedTradesResults = {trade["symbol"]: trade["profit"] + trade["storage"] + trade["commission"]
                                    for trade in self.openedTradesFullInfo
                                    }
        self.openedTradesOpenTimes = {trade["symbol"]: trade["open_time"]
                                      for trade in self.openedTradesFullInfo
                                      }

    def check_current_trades_get_unique(self, possibleTradesDict):
        currentTradesCurrencies = BullsAndBears.split_pairs_to_currencies(
            list(self.openedTradesOnlyPairs.keys()))

        toRemove = []
        for pair in possibleTradesDict:
            if pair[0:3] in currentTradesCurrencies or \
                    pair[3:6] in currentTradesCurrencies:
                toRemove.append(pair)

        possibleTradesDict = {pair: possibleTradesDict[pair]
                              for pair in possibleTradesDict
                              if pair not in toRemove
                              }
        return possibleTradesDict

    def close_trades(self, client, tradesToClose):

        for pair in tradesToClose:
            Trade(client, self.openedTradesOnlyPairs[pair], "close", pair,
                  self.openedTradesVolumes[pair], self.openedTradesOpeningPrices[pair],
                  order=self.openedTradesOrdersNo[pair])


class AddPosition:

    def __init__(self, accountData, currentTrades, bidAsk):

        volumesByDirection = {pair.split()[0]: {"buy": [], "sell": []}
                              for pair in currentTrades.openedTradesOnlyPairs}

        # volumesByDirection = {"buy": [], "sell": []}
        pairsByDirections = {"buy": [], "sell": []}
        for pair in currentTrades.openedTradesOnlyPairs:
            if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                pairsByDirections["buy"].append(pair)

            elif currentTrades.openedTradesOnlyPairs[pair] == "sell":
                pairsByDirections["sell"].append(pair)

        for direction in pairsByDirections:
            for pair in currentTrades.openedTradesVolumes:
                if direction == currentTrades.openedTradesOnlyPairs[pair]:
                    volumesByDirection[pair.split()[0]][direction].append(
                        currentTrades.openedTradesVolumes[pair])

        smallestVolumes = {pair: {direction: max(volumesByDirection[pair][direction])
                                  for direction in volumesByDirection[pair]
                                  if sum(volumesByDirection[pair][direction]) > 0}
                           for pair in volumesByDirection}

        summaryVolumes = {pair: {direction: round(sum(volumesByDirection[pair][direction]), 2)
                                 for direction in volumesByDirection[pair]
                                 }
                          for pair in volumesByDirection
                          }

        volumes = []
        for pair in summaryVolumes:
            for direction in summaryVolumes[pair]:
                volumes.append(summaryVolumes[pair][direction])

        self.maxVolume = max(volumes)
        self.summaryVolumes = summaryVolumes
        self.smallestVolumes = smallestVolumes

    def check_if_trade_is_in_margin_limit(self, volume, direction, accountData, currencyExchangePLN, pair):
        currentMarginLevel = accountData.marginLevel
        totalVolume = self.summaryVolumes[direction] + volume
        calculatedMargin = (accountData.equity * 30) / \
            (1000 * totalVolume * currencyExchangePLN[pair])
        if calculatedMargin >= 160:
            return True


class Trade:

    def __init__(self, client, buyORsell, openORclose, pair,
                 volume, price=1, stopLoss=None, takeProfit=None,
                 order=None):
        cmdField = {
            "buy": 0,
            "sell": 1,
            "buylimit": 2,
            "selllimit": 3,
            "buystop": 4,
            "sellstop": 5
        }

        typeField = {
            "open": 0,
            "close": 2,
            "modify": 3
        }

        tradeTransInfo = {
            "symbol": pair.split()[0],
            "type": typeField[openORclose],
            "cmd": cmdField[buyORsell],
            "customComment": None,
            "expiration": None,
            "offset": 0,
            "order": order,
            "price": price,
            "sl": stopLoss,
            "tp": takeProfit,
            "volume": volume
        }

        arguments = {
            "tradeTransInfo": tradeTransInfo
        }

        self.response = client.commandExecute(
            "tradeTransaction", arguments)


class PositionParameters:

    def __init__(self, client, possibleTradesWithAllOk, currencyExchangePLN,
                 equity, currentTrades, smallestVolumes, hedge=False, volume=0, simulation=None):

        self.positionTP = {}
        self.positionSL = {}
        self.positionLots = {}
        self.tradesToExecute = {}

        self.allOkTrades = possibleTradesWithAllOk

        bidAsk = BidAsk(client, possibleTradesWithAllOk)

        for pair in possibleTradesWithAllOk:

            if "JPY" in pair:
                decimals = 3
            else:
                decimals = 5

            if possibleTradesWithAllOk[pair] == "buy":

                # if bidAsk.bidPrices[pair] > localResistanceDict[pair]:
                self.positionSL[pair] = 0
                self.positionTP[pair] = 0

                self.tradesToExecute[pair] = possibleTradesWithAllOk[pair]

                if hedge == False and volume == 0:
                    if simulation.positionSizes[0] < 0.01:
                        self.positionLots[pair] = 0.01
                    else:
                        self.positionLots[pair] = simulation.positionSizes[0]
                elif volume != 0:
                    self.positionLots[pair] = volume
                elif hedge != False:
                    if truncate(smallestVolumes[pair]["sell"] * 0.9, 2) <= truncate(simulation.positionSizes[0] / 10, 2):
                        self.positionLots[pair] = simulation.positionSizes[0]
                    else:
                        self.positionLots[pair] = truncate(
                            smallestVolumes[pair]["sell"] * 0.9, 2)

            elif possibleTradesWithAllOk[pair] == "sell":

                # if bidAsk.bidPrices[pair] > localResistanceDict[pair]:
                self.positionSL[pair] = 0
                self.positionTP[pair] = 0

                self.tradesToExecute[pair] = possibleTradesWithAllOk[pair]
                if hedge == False and volume == 0:
                    if simulation.positionSizes[0] < 0.01:
                        self.positionLots[pair] = 0.01
                    else:
                        self.positionLots[pair] = simulation.positionSizes[0]
                elif volume != 0:
                    self.positionLots[pair] = volume
                elif hedge != False:
                    if truncate(smallestVolumes[pair]["buy"] * 0.9, 2) <= truncate(simulation.positionSizes[0] / 10, 2):
                        self.positionLots[pair] = simulation.positionSizes[0]
                    else:
                        self.positionLots[pair] = truncate(
                            smallestVolumes[pair]["buy"] * 0.9, 2)

    def execute_trades(self, client):

        print("self.tradesToExecute:", self.tradesToExecute)

        for pair in self.tradesToExecute:
            Trade(client, self.tradesToExecute[pair], "open", pair, self.positionLots[pair],
                  stopLoss=self.positionSL[pair], takeProfit=self.positionTP[pair])
            time.sleep(1)


class Hedge:

    @staticmethod
    def check_hedge_with_current_trades_for_duplicates(currentTrades):
        currentDirections = {}

        uniquePairs = []
        for pair in currentTrades:
            uniquePairs.append(pair.split()[0])
        uniquePairs = list(set(uniquePairs))

        for pair in uniquePairs:
            currentDirections[pair] = []

        for pair in currentTrades:
            currentDirections[pair.split()[0]].append(currentTrades[pair])

        currentDirectionsSet = {pair: list(set(currentDirections[pair]))
                                for pair in currentDirections
                                }

        return currentDirectionsSet

    @staticmethod
    def reverse_directions_for_hedge(currentTradesDirections):
        hedgeDirections = {}

        if "buy" in list(currentTradesDirections.values()) and "sell" in list(currentTradesDirections.values()):
            return {}
        else:
            for pair in currentTradesDirections:
                if currentTradesDirections[pair] == "sell":
                    hedgeDirections[pair.split()[0]] = "buy"
                elif currentTradesDirections[pair] == "buy":
                    hedgeDirections[pair.split()[0]] = "sell"
            return hedgeDirections


class BidAsk:

    def __init__(self, client, pairList):

        self.bidPrices = {}
        self.askPrices = {}
        self.spreads = {}
        self.swapsLong = {}
        self.swapsShort = {}

        for pair in pairList:
            arguments = {
                "symbol":  pair.split()[0]
            }
            response = client.commandExecute(
                "getSymbol", arguments)["returnData"]

            self.swapsLong[pair] = response["swapLong"]
            self.swapsShort[pair] = response["swapShort"]
            self.bidPrices[pair] = response["bid"]
            self.askPrices[pair] = response["ask"]
            self.spreads[pair] = round(response["ask"] - response["bid"], 5)
            # time.sleep(1)


class Trends:

    def __init__(self, resistanceDict, supportDict, highLows):

        firstResistanceDirections = {pair: Trends.calculate_trend_progression(resistanceDict[pair][0],
                                                                              resistanceDict[pair][1],
                                                                              highLows[pair])
                                     for pair in resistanceDict
                                     }

        firstSupportDirections = {pair: Trends.calculate_trend_progression(supportDict[pair][0],
                                                                           supportDict[pair][1],
                                                                           highLows[pair])
                                  for pair in supportDict
                                  }

        secondResistanceDirections = {pair: Trends.calculate_trend_progression(resistanceDict[pair][0],
                                                                               resistanceDict[pair][2],
                                                                               highLows[pair])
                                      for pair in resistanceDict
                                      }

        secondSupportDirections = {pair: Trends.calculate_trend_progression(resistanceDict[pair][0],
                                                                            resistanceDict[pair][2],
                                                                            highLows[pair])
                                   for pair in supportDict
                                   }
        trendRanks = {pair: Trends.get_trend_rank(pair, firstResistanceDirections,
                                                  firstSupportDirections,
                                                  secondResistanceDirections,
                                                  secondSupportDirections)
                      for pair in supportDict
                      }

        self.trendsDict = {}
        for pair in trendRanks:
            if trendRanks[pair] > 1:
                self.trendsDict[pair] = "uptrend"
            elif trendRanks[pair] < 1:
                self.trendsDict[pair] = "downtrend"
            else:
                self.trendsDict[pair] = "side"

    @staticmethod
    def calculate_trend_progression(firstLevel, secondLevel, highLows):
        if firstLevel - secondLevel >= highLows and firstLevel - secondLevel > 0:
            return 1
        elif math.fabs(firstLevel - secondLevel) < highLows:
            return 0
        elif secondLevel - firstLevel >= highLows and secondLevel - firstLevel > 0:
            return -1

    @staticmethod
    def get_trend_rank(pair, firstDict, secondDict, thirdDict, fourthDict):

        rankList = []
        if pair in firstDict:
            rankList.append(firstDict[pair])
        if pair in secondDict:
            rankList.append(secondDict[pair])
        if pair in thirdDict:
            rankList.append(thirdDict[pair])
        if pair in fourthDict:
            rankList.append(fourthDict[pair])
        return sum(rankList)

    def check_trades_and_trends(self, tradesDict):

        tradesDirectionsInTrends = {
            "uptrend": "buy", "downtrend": "sell", "side": "both"}

        self.updatedPossibleTradesDict = {pair: tradesDirectionsInTrends[self.trendsDict[pair]]
                                          for pair in tradesDict
                                          if tradesDict[pair] == tradesDirectionsInTrends[self.trendsDict[pair]] or
                                          tradesDict[pair] == "both" or self.trendsDict[pair] == "side"
                                          }

        return self.updatedPossibleTradesDict


class FreeCurrencyConverter:

    @staticmethod
    def get_PLN_exchange_rate(possibleTradesWithAllOk):

        exchangeRatesJson = requests.get(
            "https://api.nbp.pl/api/exchangerates/tables/A?format=json", timeout=5).json()[0]["rates"]

        exchangeRates = {rate["code"]: rate["mid"]
                         for rate in exchangeRatesJson
                         }

        return {pair: exchangeRates[pair[0:3]]
                for pair in possibleTradesWithAllOk
                }


class TrailingStopLoss:

    def update_stop_loss(self, client, currentTrades, averageOpeningPricesByDirection, stopLosses, stopLossStep, isJPYinPair=False):

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        bidAsk = BidAsk(client, currentTrades.openedTradesOnlyPairs)

        stopLossValuesForUpdatingTrades = {}

        print("currentTrades.openedTradesOpeningPrices",
              currentTrades.openedTradesOpeningPrices)

        for pair in averageOpeningPricesByDirection:

            for direction in averageOpeningPricesByDirection[pair]:

                if direction == "buy":
                    if bidAsk.bidPrices[pair] - averageOpeningPricesByDirection[pair]["buy"] >= stopLossStep * pipValue:
                        try:
                            if stopLosses[pair]["buy"] > 0:
                                stopLossValuesForUpdatingTrades[pair] = {
                                    "buy": round(stopLosses[pair]["buy"] + stopLossStep * pipValue, 5)}
                            else:
                                stopLossValuesForUpdatingTrades[pair] = {"buy": round(
                                    averageOpeningPricesByDirection[pair]["buy"] + stopLossStep * pipValue, 5)}
                        except KeyError:
                            pass

                if direction == "sell":
                    if averageOpeningPricesByDirection[pair]["sell"] - bidAsk.bidPrices[pair] >= stopLossStep * pipValue:
                        try:
                            if stopLosses[pair]["sell"] > 0:
                                stopLossValuesForUpdatingTrades[pair] = {"sell": round(
                                    stopLosses[pair]["sell"] - stopLossStep * pipValue, 5)}
                            else:
                                stopLossValuesForUpdatingTrades[pair] = {"sell": round(
                                    averageOpeningPricesByDirection[pair]["sell"] - stopLossStep * pipValue, 5)}
                        except KeyError:
                            pass

        print("stopLossValuesForUpdatingTrades",
              stopLossValuesForUpdatingTrades)

        stopLossValues = {}
        for pair in currentTrades.openedTradesOnlyPairs:

            if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                try:
                    stopLossValues[pair] = stopLossValuesForUpdatingTrades[pair.split()[
                        0]]["buy"]
                except KeyError:
                    stopLossValues[pair] = 0

            if currentTrades.openedTradesOnlyPairs[pair] == "sell":
                try:
                    stopLossValues[pair] = stopLossValuesForUpdatingTrades[pair.split()[
                        0]]["sell"]
                except KeyError:
                    stopLossValues[pair] = 0

        return stopLossValues

    def execute_update_stoploss(self, client, currentTrades, stopLossToUpdate):
        for pair in stopLossToUpdate:

            Trade(client, currentTrades.openedTradesOnlyPairs[pair], "modify", pair.split()[0],
                  currentTrades.openedTradesVolumes[pair], price=currentTrades.openedTradesOpeningPrices[pair],
                  stopLoss=stopLossToUpdate[pair], takeProfit=currentTrades.openedTradesTakeProfit[pair],
                  order=currentTrades.openedTradesOrdersNo[pair])
            time.sleep(1)

    @staticmethod
    def get_last_chart_reversal_index(listName):
        indexes = [number
                   for number in range(len(listName))
                   if listName[number] == 0
                   ]
        return indexes[-1]

    @staticmethod
    def get_chart_reversals_indexes(listName):
        indexes = [number
                   for number in range(len(listName))
                   if listName[number] == 0
                   ]
        return indexes

    @staticmethod
    def get_last_proper_reversals(tradingPairsCurrentClosePrices, directionOfCharts, highLows, currentTrades):
        reversalsIndexes = {pair: TrailingStopLoss.get_chart_reversals_indexes(directionOfCharts[pair])
                            for pair in directionOfCharts
                            }
        lastReversals = {}

        for pair in directionOfCharts:
            for index in list(reversed(reversalsIndexes[pair])):
                if math.fabs(tradingPairsCurrentClosePrices[pair][-1] - tradingPairsCurrentClosePrices[pair][index]) >= highLows[pair]:

                    if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                        if tradingPairsCurrentClosePrices[pair][-1] > tradingPairsCurrentClosePrices[pair][index]:
                            lastReversals[pair] = tradingPairsCurrentClosePrices[pair][index]

                    elif currentTrades.openedTradesOnlyPairs[pair] == "sell":
                        if tradingPairsCurrentClosePrices[pair][-1] < tradingPairsCurrentClosePrices[pair][index]:
                            lastReversals[pair] = tradingPairsCurrentClosePrices[pair][index]
                    break

        return lastReversals


def data_frame_date_conversion(date):
    return int(date) / 1000000000


def show_values_on_bars(axs):
    def _show_on_single_plot(ax):
        for p in ax.patches:
            _x = p.get_x() + p.get_width() / 2
            _y = p.get_y() + p.get_height()
            value = '{:.2f}'.format(p.get_height())
            ax.text(_x, _y, value, ha="center")

    if isinstance(axs, np.ndarray):
        for idx, ax in np.ndenumerate(axs):
            _show_on_single_plot(ax)
    else:
        _show_on_single_plot(axs)


def convert_hours_to_full_time(tradeTimeDecimal):
    hour = int(tradeTimeDecimal)
    minute = int(
        (tradeTimeDecimal - int(tradeTimeDecimal))*60.0)
    second = int(((tradeTimeDecimal - int(tradeTimeDecimal))*60 -
                  int((tradeTimeDecimal - int(tradeTimeDecimal))*60.0))*60.0)
    return datetimeTime.timedelta(hours=hour, minutes=minute, seconds=second)


class DepositWithdrawals:

    def __init__(self, client, initialDeposit, balance, provisionRate, userId):
        cmds = {0: "buy", 1: "sell"}

        first_day_of_month = str("2020-08-01") + " 00:00:00"
        # daty start/koniec w formacie timestamp
        last_day_of_month = str(datetime.today().date().replace(
            day=1) + relativedelta(months=+1) - timedelta(days=1))

        startDateTimestampHistory = int(datetime.timestamp(
            datetime.strptime(first_day_of_month, '%Y-%m-%d %H:%M:%S')))*1000
        History_info = {
            "end": 0,
            "start": startDateTimestampHistory
        }

        historyResponse = client.commandExecute(
            "getTradesHistory", History_info)["returnData"]

        self.totalProfit = 0
        self.totalCommmission = 0
        self.totalStorage = 0
        for trade in historyResponse:
            self.totalProfit += trade["profit"]
            self.totalCommmission += trade["commission"]
            self.totalStorage += trade["storage"]

        self.totalProfit = self.totalProfit + self.totalCommmission + self.totalStorage

        self.provision = provisionRate * self.totalProfit
        print("self.provision", self.provision)

        try:
            paid_provisions = FileSupport.read_file(
                "paid_provisions", support=True)[str(userId)]
        except:
            paid_provisions = 0
        print("paid_provisions", paid_provisions)

        if self.provision - paid_provisions > 0:
            self.provision_due = round(self.provision - paid_provisions, 2)
        else:
            self.provision_due = 0

        print("self.provision_due", self.provision_due)
        try:
            provision_dictionary = FileSupport.read_file(str(userId))
            provision_dictionary[last_day_of_month] = self.provision_due
        except:
            provision_dictionary = {last_day_of_month: self.provision_due}

        FileSupport.save_file(str(userId), provision_dictionary)

        """

        if balance - initialDeposit - self.totalProfit < 0:
            self.totalDeposits = 0
            self.totalWithdrawals = -1 * \
                (balance - initialDeposit - self.totalProfit)
        else:
            self.totalDeposits = balance - initialDeposit - self.totalProfit
            self.totalWithdrawals = 0

        if self.totalWithdrawals > initialDeposit:
            self.provision = provisionRate * \
                (self.totalWithdrawals - initialDeposit)
        else:
            self.provision = 0
        print("balance", balance)
        print("initialDeposit", initialDeposit)
        print("self.totalProfit", self.totalProfit)
        print("self.totalDeposits", self.totalDeposits)
        print("self.totalWithdrawals", self.totalWithdrawals)


        paid_provisions = FileSupport.read_file(
            "paid_provisions", support=True)[str(userId)]

        if self.provision - paid_provisions > 0:
            self.provision_due = self.provision - paid_provisions
        else:
            self.provision_due = 0

        print("self.provision_due",self.provision_due)

        print(paid_provisions)
        input()
        """


class TradeHistory:

    def __init__(self, client, nowTime, today, facebookMode, isJPYinPair=False):

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        cmds = {0: "buy", 1: "sell"}

        timeDiff = timedelta(days=0)
        """
        startTimeHistory = str(
            datetime.today().date() - timeDiff) + " 00:00:00"

        # daty start/koniec w formacie timestamp

        startDateTimestampHistory = int(datetime.timestamp(
            datetime.strptime(startTimeHistory, '%Y-%m-%d %H:%M:%S')))*1000
        """

        first_day_of_month = str(
            datetime.today().date().replace(day=1)) + " 00:00:00"
        # daty start/koniec w formacie timestamp
        startDateTimestampHistory = int(datetime.timestamp(
            datetime.strptime(first_day_of_month, '%Y-%m-%d %H:%M:%S')))*1000

        History_info = {
            "end": 0,
            "start": startDateTimestampHistory
        }

        historyResponse = client.commandExecute(
            "getTradesHistory", History_info)["returnData"]

        if today == "fri":
            chartSendingHour = "21:45"
        else:
            chartSendingHour = "23:45"

        try:

            historyDataFrame = pd.json_normalize(historyResponse)

            historyDataFrame["date"] = historyDataFrame["close_time"].apply(
                lambda x: str(datetime.fromtimestamp(int(x) / 1000).strftime("%Y-%m-%d")))
            historyDataFrame["trade_duration"] = historyDataFrame["close_time"].apply(lambda x: datetime.fromtimestamp(
                x / 1000)) - historyDataFrame["open_time"].apply(lambda x: datetime.fromtimestamp(x / 1000))
            historyDataFrame["average_duration_of_trade_in_hours"] = historyDataFrame["trade_duration"].apply(
                lambda x: x.total_seconds() / 3600)
            historyDataFrame["nettoProfit"] = historyDataFrame["profit"] + \
                historyDataFrame["storage"] + historyDataFrame["commission"]
            # float(historyDataFrame["commission"]) - float(historyDataFrame["storage"])

            profitByDays = historyDataFrame.groupby(
                ["date"], as_index=False)["nettoProfit"].sum()

            tradesDurationByDays = historyDataFrame.groupby(
                ["date"], as_index=False)["average_duration_of_trade_in_hours"].mean()

            tradesDurationByDays["average_duration_of_trade_full_time"] = tradesDurationByDays["average_duration_of_trade_in_hours"]

            tradesDurationByDays["average_duration_of_trade_full_time"] = tradesDurationByDays["average_duration_of_trade_full_time"].apply(
                convert_hours_to_full_time)

            # obliczenie średniego zysku z dzisiejszej pozycji
            todayAverageProfit = historyDataFrame[historyDataFrame["date"] == str(
                datetime.today().date())]["nettoProfit"].mean()
            if str(todayAverageProfit) == "nan":
                self.todayAverageProfit = 0
            else:
                self.todayAverageProfit = todayAverageProfit

            # obliczenie ilości dzisiejszych pozycji
            self.todayNumberOfPositions = historyDataFrame[historyDataFrame["date"] == str(
                datetime.today().date())]["nettoProfit"].count()

            """
            if nowTime == chartSendingHour:

                tradesByDays = historyDataFrame.groupby(
                    ["date"], as_index=False)["nettoProfit"].count()

                # profitByDays["profit2"] = profitByDays["profit"].apply(lambda x: str(round(x, 2)) + "zł")

                fig, ax = plt.subplots(figsize=(10, 10))

                profitByDaysChart = sns.barplot(
                    x="date", y="nettoProfit", data=profitByDays, palette="Blues_d", ax=ax)
                tradesByDaysChart = sns.barplot(x="date", y="nettoProfit",
                                                data=tradesByDays, palette="Greens_d", ax=ax)

                # naniesienie wartości na profitByDaysChart i stopniowanie kolorów słupków

                groupedvalues = profitByDays.reset_index()
                pal = sns.color_palette("Blues_d")
                groupedvalues["extra"] = 0
                rank = groupedvalues["extra"]
                g = sns.barplot(x='date', y='nettoProfit', data=groupedvalues,
                                palette=np.array(pal[::-1])[rank])
                for index, row in groupedvalues.iterrows():
                    g.text(row.name, row.nettoProfit,
                           round(row.nettoProfit, 2), color='black', ha="center")

                # naniesienie wartości na tradesByDaysChart i stopniowanie kolorów słupków
                groupedvalues = tradesByDays.reset_index()
                pal = sns.color_palette("Greens_d")
                groupedvalues["extra"] = 3
                rank = groupedvalues["extra"]
                g = sns.barplot(x='date', y='nettoProfit', data=groupedvalues,
                                palette=np.array(pal[::-1])[rank])
                for index, row in groupedvalues.iterrows():
                    g.text(row.name, row.nettoProfit, round(
                        row.nettoProfit, 2), color='black', ha="center")

                ax.grid(True)
                ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
                plt.figure(figsize=(10, 10))
                tradesByDaysChart.set_xticklabels(
                    tradesByDaysChart.get_xticklabels(), rotation=90, horizontalalignment='right')
                fig = profitByDaysChart.get_figure()
                fig.savefig("profits_by_days.jpg", dpi=100)

                # ================
                fig, ax = plt.subplots(figsize=(10, 10))
                tradesDurationByDaysChart = sns.barplot(x="date", y="average_duration_of_trade_in_hours",
                                                        data=tradesDurationByDays, palette="Oranges_d", ax=ax)

                # naniesienie wartości na tradesDurationByDaysChart i stopniowanie kolorów słupków
                groupedvalues = tradesDurationByDays.reset_index()
                pal = sns.color_palette("Oranges_d")
                groupedvalues["extra"] = 3
                rank = groupedvalues["extra"]
                g = sns.barplot(x='date', y='average_duration_of_trade_in_hours', data=groupedvalues,
                                palette=np.array(pal[::-1])[rank])
                for index, row in groupedvalues.iterrows():
                    g.text(row.name, row.average_duration_of_trade_in_hours, round(
                        row.average_duration_of_trade_in_hours, 2), color='black', ha="center")
                ax.grid(True)
                ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
                plt.figure(figsize=(10, 10))
                tradesDurationByDaysChart.set_xticklabels(
                    tradesByDaysChart.get_xticklabels(), rotation=90, horizontalalignment='right')
                fig = tradesDurationByDaysChart.get_figure()
                fig.savefig("duration_by_days.jpg", dpi=100)

                # self.averageDailyProfit = str(round(profitByDays.mean()["profit"], 2)) + " PLN"

            else:
                # self.averageDailyProfit = str(round(profitByDays.mean()["profit"], 2)) + " PLN"
                pass
            """

            tradeHistory = {}
            todayProfit = 0
            monthProfit = 0
            amountOfDouble = 0
            amountOfTrades = 0
            todayTimesOfTrades = []
            monthTradeTimes = []

            data = {"NR": [],
                    "CENA OTW.": [],
                    "CZAS. OTW.": [],
                    "CZAS. ZAMKN.": [],
                    "CZAS TRWANIA": [],
                    "PARA": [],
                    "KIERUNEK": [],
                    "WOLUMEN": [],
                    "ZYSK PIPS": [],
                    "ZYSK KWOTA": []}
            sum = 0

            for trade in historyResponse:
                if trade["close_time"] == None:
                    pass
                else:
                    if str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m")) == str(datetime.today().date().strftime("%Y-%m")):
                        sum += 1
            if sum != 0:
                tradeHistoryDataFrame = pd.DataFrame(data)

            else:
                tradeHistoryDataFrame = None

            number = 1

            if nowTime == chartSendingHour:
                for trade in list(reversed(historyResponse)):
                    if trade["close_time"] == None:
                        pass
                    else:
                        if str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m")) == str(datetime.today().date().strftime("%Y-%m")):

                            if str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m-%d")) == str(datetime.today().date()):
                                todayProfit += trade["profit"]
                                todayProfit += trade["storage"]
                                todayProfit += trade["commission"]

                            tradeTimeDecimal = ((datetime.fromtimestamp(
                                trade["close_time"] / 1000) - datetime.fromtimestamp(trade["open_time"] / 1000)).total_seconds() / 3600)
                            hour = int(tradeTimeDecimal)
                            minute = int(
                                (tradeTimeDecimal - int(tradeTimeDecimal))*60.0)
                            second = int(((tradeTimeDecimal - int(tradeTimeDecimal))*60 -
                                          int((tradeTimeDecimal - int(tradeTimeDecimal))*60.0))*60.0)
                            timeOfTrade = str(
                                datetimeTime.timedelta(hours=hour, minutes=minute, seconds=second))
                            todayTimesOfTrades.append(tradeTimeDecimal)

                            tradeHistoryDataFrame = tradeHistoryDataFrame.append({"NR": str(number),
                                                                                  "CENA OTW.": str(trade["open_price"]),
                                                                                  "CZAS. OTW.": str(datetime.fromtimestamp(trade["open_time"] / 1000).strftime("%Y-%m-%d %H:%M")),
                                                                                  "CZAS. ZAMKN.": str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m-%d %H:%M")),
                                                                                  "CZAS TRWANIA": timeOfTrade,
                                                                                  "PARA": str(trade["symbol"]),
                                                                                  "KIERUNEK": str(cmds[int(trade["cmd"])]),
                                                                                  "WOLUMEN": str(trade["volume"]),
                                                                                  "ZYSK PIPS": str(round(math.fabs(trade["close_price"] - trade["open_price"]) / pipValue, 1)),
                                                                                  "ZYSK KWOTA": (str(round(trade["profit"] + trade["storage"] + trade["commission"], 2)) + " PLN")}, ignore_index=True)
                            number += 1

                # tradeHistoryDataFrame = tradeHistoryDataFrame.set_index("NR")

                if facebookMode:
                    tradeHistoryPlot = renderDataFrameImage(
                        tradeHistoryDataFrame, header_columns=0)
                    fig = tradeHistoryPlot.get_figure()
                    fig.savefig("month_statement.jpg", dpi=100)

            else:
                for trade in list(reversed(historyResponse)):
                    if trade["close_time"] == None:
                        pass
                    else:
                        if str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m-%d")) == str(datetime.today().date()):

                            todayProfit += trade["profit"]
                            todayProfit += trade["storage"]
                            todayProfit += trade["commission"]

                            tradeTimeDecimal = ((datetime.fromtimestamp(
                                trade["close_time"] / 1000) - datetime.fromtimestamp(trade["open_time"] / 1000)).total_seconds() / 3600)
                            hour = int(tradeTimeDecimal)
                            minute = int(
                                (tradeTimeDecimal - int(tradeTimeDecimal))*60.0)
                            second = int(((tradeTimeDecimal - int(tradeTimeDecimal))*60 -
                                          int((tradeTimeDecimal - int(tradeTimeDecimal))*60.0))*60.0)
                            timeOfTrade = str(
                                datetimeTime.timedelta(hours=hour, minutes=minute, seconds=second))
                            todayTimesOfTrades.append(tradeTimeDecimal)

                            tradeHistoryDataFrame = tradeHistoryDataFrame.append({"NR": str(number),
                                                                                  "CENA OTW.": str(trade["open_price"]),
                                                                                  "CZAS. OTW.": str(datetime.fromtimestamp(trade["open_time"] / 1000).strftime("%Y-%m-%d %H:%M")),
                                                                                  "CZAS. ZAMKN.": str(datetime.fromtimestamp(trade["close_time"] / 1000).strftime("%Y-%m-%d %H:%M")),
                                                                                  "CZAS TRWANIA": timeOfTrade,
                                                                                  "PARA": str(trade["symbol"]),
                                                                                  "KIERUNEK": str(cmds[int(trade["cmd"])]),
                                                                                  "WOLUMEN": str(trade["volume"]),
                                                                                  "ZYSK PIPS": str(round(math.fabs(trade["close_price"] - trade["open_price"]) / pipValue, 1)),
                                                                                  "ZYSK KWOTA": (str(round(trade["profit"] + trade["storage"] + trade["commission"], 2)) + " PLN")}, ignore_index=True)
                            number += 1

                tradeHistoryDataFrame = tradeHistoryDataFrame.drop(
                    columns="NR")
                tradeHistoryDataFrame.columns.name = "NR"
                tradeHistoryDataFrame.index = np.arange(
                    1, len(tradeHistoryDataFrame)+1)

            for trade in historyResponse:
                if trade["close_time"] == None:
                    pass
                else:
                    monthProfit += trade["profit"]
                    monthProfit += trade["storage"]
                    monthProfit += trade["commission"]

                    tradeTimeDecimal = ((datetime.fromtimestamp(
                        trade["close_time"] / 1000) - datetime.fromtimestamp(trade["open_time"] / 1000)).total_seconds() / 3600)

                    monthTradeTimes.append(tradeTimeDecimal)

                    amountOfTrades += 1
                    if trade["profit"] < 0:
                        amountOfDouble += 1

            self.tradeHistory = tradeHistory
            self.todayProfit = round(todayProfit, 2)
            self.monthProfit = round(monthProfit, 2)
            self.averageDailyProfit = str(round(self.monthProfit / np.busday_count(str(datetime.today().replace(day=1).strftime("%Y-%m-%d")),
                                                                                   str(datetime.today().strftime("%Y-%m-%d"))), 2)) + " PLN"

            # średnia dzienna ilość pozycji w miesiącu
            self.averageNumberOfPositionsPerDay = round(
                amountOfTrades / np.busday_count(str(datetime.today().replace(day=1).strftime("%Y-%m-%d")),
                                                 str(datetime.today().strftime("%Y-%m-%d"))), 2)

            try:
                # obliczenie śr czasu trwania trejdu M-C
                monthAverageTimeDecimal = pd.Series(
                    data=monthTradeTimes).mean()
                hour = int(monthAverageTimeDecimal)
                minute = int(
                    (monthAverageTimeDecimal - int(monthAverageTimeDecimal))*60.0)
                second = int(((monthAverageTimeDecimal - int(monthAverageTimeDecimal))*60 -
                              int((monthAverageTimeDecimal - int(monthAverageTimeDecimal))*60.0))*60.0)

                averageMonthTradeTime = str(
                    datetimeTime.timedelta(hours=hour, minutes=minute, seconds=second))

            except ValueError:
                averageMonthTradeTime = 0

            try:
                # obliczenie śr czasu trwania trejdu DZIŚ
                todayAverageTimeDecimal = pd.Series(
                    data=todayTimesOfTrades).mean()
                hour = int(todayAverageTimeDecimal)
                minute = int(
                    (todayAverageTimeDecimal - int(todayAverageTimeDecimal))*60.0)
                second = int(((todayAverageTimeDecimal - int(todayAverageTimeDecimal))*60 -
                              int((todayAverageTimeDecimal - int(todayAverageTimeDecimal))*60.0))*60.0)
                averageTodayTradeTime = str(
                    datetimeTime.timedelta(hours=hour, minutes=minute, seconds=second))

            except ValueError:
                averageTodayTradeTime = 0

            self.averageTodayTradeTime = averageTodayTradeTime
            self.averageMonthTradeTime = averageMonthTradeTime
            self.amountOfDouble = amountOfDouble
            self.amountOfTrades = amountOfTrades
            if sum == 0:
                self.tradeHistoryDataFrame = []
            else:
                self.tradeHistoryDataFrame = tradeHistoryDataFrame

        except:
            self.todayProfit = 0
            self.monthProfit = 0
            self.averageDailyProfit = "0 PLN"
            self.averageNumberOfPositionsPerDay = 0
            self.averageTodayTradeTime = 0
            self.averageMonthTradeTime = 0
            self.amountOfDouble = 0
            self.amountOfTrades = 0
            self.tradeHistoryDataFrame = []
            self.todayAverageProfit = 0
            self.todayNumberOfPositions = 0


def max_dist(equity, lot, XXXYYY, leverage, openPrice, pipValue, parameter=False):
    # round(openPrice * (equity - (lot * 100000 * XXXYYY / (2 * leverage))) / (lot * 100000 * XXXYYY * pipValue), 2)
    # return round(((equity - (lot * 100000 * XXXYYY) / leverage) * openPrice) / (100000 * XXXYYY * lot) / pipValue, 2)
    if parameter == True:
        return round((equity - (lot * 100000 * XXXYYY) / leverage) * openPrice / (lot * 100000 * XXXYYY) / pipValue, 2)
    else:
        return round((equity) * openPrice / (lot * 100000 * XXXYYY) / pipValue, 2)


def max_lot(equity, maxDist, XXXYYY, openPrice, leverage, pipValue):
    # return truncate(equity / ((maxDist * 100000 * XXXYYY * pipValue / openPrice) + (100000 * XXXYYY / (2 * leverage))), 2)
    return truncate((equity * openPrice)/(maxDist * pipValue * 100000 * XXXYYY * (1 + (openPrice / (leverage * maxDist * pipValue)))), 2)


def calc_loss(openPrice, currentprice, lot, XXXYYY):
    # return round(math.fabs((currentprice - openPrice) / openPrice * lot * 100000 * XXXYYY), 2)
    return round((currentprice - openPrice) * 100000 * XXXYYY * lot / openPrice, 2)


def get_multipier_volumes(firstMultiplier, allMultiplier, lot, amountOfAprox):

    if allMultiplier != None:
        quotient = (1 + allMultiplier) / allMultiplier
        volumes = [lot]
        start = lot
        for _ in range(amountOfAprox):
            volumes.append(truncate(start - start / quotient, 2))
            start = start - start / quotient
        return list(reversed(volumes))

    elif firstMultiplier != None:
        posSize = lot / (firstMultiplier + amountOfAprox)
        return list(np.linspace(posSize * firstMultiplier, lot, amountOfAprox + 1))


def get_positions_sizes_for_aprox(volumes):

    positionSizes = []
    index = 0
    for volume in volumes:
        if volumes.index(volume) == 0:
            positionSizes.append(truncate(volume, 2))
        else:
            index += 1
            positionSizes.append(
                round(volumes[index] - volumes[index - 1], 2))
    return positionSizes


class Simulation:

    def __init__(self, equity, openPrice, amountOfAprox, distOfAprox,  XXXYYY, leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist=None, lot=None):

        totalLoss = 0

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        if maxDist == None and lot != None:
            self.maxPossibleDist = max_dist(
                equity, lot, XXXYYY, leverage, openPrice, pipValue, parameter=True)
            self.maxPossibleLot = lot
        elif maxDist != None and lot == None:
            self.maxPossibleDist = maxDist
            self.maxPossibleLot = max_lot(
                equity, maxDist, XXXYYY, openPrice, leverage, pipValue)
            print("self.maxPossibleLot ", self.maxPossibleLot)
        elif maxDist != None and lot != None:
            print(
                "Only one varbiable allowed: \"lot\" or \"maxDist\". Can't be both")
            sys.exit()
        elif maxDist == None and lot == None:
            print(
                "No \"lot\" or \"maxDist\" variable. One must be given")
            sys.exit()
        elif firstMultiplier != None and allMultiplier != None:
            print("There can be only one multiplier type")
            sys.exit()

        try:
            try:
                volumes = get_multipier_volumes(
                    firstMultiplier, allMultiplier, self.maxPossibleLot, amountOfAprox)

            except ZeroDivisionError:
                volumes = [self.maxPossibleLot]

            print("volumes", volumes)
            positionSizes = get_positions_sizes_for_aprox(volumes)
            print("positionSizes", positionSizes)

            index = 0
            nextPrice = openPrice
            priceTimesVolume = 0

            maxLoss = equity - (self.maxPossibleLot *
                                100000 * XXXYYY / leverage) / 2
            possiblePositionSizes = []
            print("maxLoss", maxLoss)

            multiplier = len(positionSizes) - 1

            for positionSize in positionSizes:

                if index == 0:

                    totalLoss = calc_loss(
                        openPrice, openPrice + distOfAprox * multiplier * pipValue, positionSize, XXXYYY)
                    priceTimesVolume = nextPrice * positionSize
                    nextPrice = openPrice + distOfAprox * pipValue
                    possiblePositionSizes.append(positionSize)

                else:

                    if totalLoss >= maxLoss:
                        break
                    else:

                        totalLoss += calc_loss(nextPrice, nextPrice + distOfAprox *
                                               multiplier * pipValue, positionSize, XXXYYY)

                        priceTimesVolume2 = nextPrice * positionSize
                        priceTimesVolume += priceTimesVolume2
                        nextPrice = nextPrice + distOfAprox * pipValue
                        possiblePositionSizes.append(positionSize)

                index += 1
                multiplier -= 1

            print("totalLoss", totalLoss)
            print("possiblePositionSizes", possiblePositionSizes)
            print("positionSizes", positionSizes)

            if possiblePositionSizes != positionSizes:
                print("Not enough funds to open all positions")

            try:
                averagePriceAfterAprox = round(
                    priceTimesVolume / (sum(positionSizes)), 5)
            except ZeroDivisionError:
                print(
                    "First position would have to be smaller than 0.01 which is impossible. Please change your parameters.")
                # sys.exit()
            print("totalLoss after last position is opened", totalLoss)

            maxDistanceAfterAprox = amountOfAprox * distOfAprox + max_dist(maxLoss - totalLoss, self.maxPossibleLot,
                                                                           XXXYYY, leverage, openPrice + amountOfAprox * distOfAprox * pipValue, pipValue)

            self.stopOutDistanceAfterAprox = truncate(maxDistanceAfterAprox, 2)
            print("maxPipsDistanceAfterLastPositionIsOpened", max_dist(maxLoss - totalLoss, self.maxPossibleLot,
                                                                       XXXYYY, leverage, openPrice + amountOfAprox * distOfAprox * pipValue, pipValue))
            print("possiblePositionSizes", possiblePositionSizes)

            if len(positionSizes) == 1:
                self.totalLoss = calc_loss(
                    openPrice, openPrice + (self.stopOutDistanceAfterAprox * pipValue), self.maxPossibleLot, XXXYYY)
            else:
                self.totalLoss = round(totalLoss, 2)

            self.averagePriceAfterAprox = averagePriceAfterAprox

            self.aproxDistanceForAverageOpeningPrice = int(truncate(math.fabs(
                openPrice - averagePriceAfterAprox) / pipValue, 0))

            self.totalPositionSizesDuringAprox = []

            for positionSize in volumes:
                self.totalPositionSizesDuringAprox.append(
                    truncate(positionSize, 2))

            self.positionSizes = positionSizes

            self.stopOutEquity = round(
                self.maxPossibleLot * 100000 * XXXYYY / leverage / 2, 2)

            self.stopOutDistanceDifference = int(truncate(
                self.stopOutDistanceAfterAprox - self.maxPossibleDist, 0))
            try:
                self.marginLevelAfterFirstOpen = round(equity *
                                                       leverage / (1000 * positionSizes[0] * XXXYYY), 2)
            except ZeroDivisionError:
                print(
                    "First position would have to be smaller than 0.01 which is impossible. Please change your parameters.")
                # sys.exit()
            self.marginLevelAfterLastOpen = round(equity *
                                                  leverage / (1000 * self.totalPositionSizesDuringAprox[-1] * XXXYYY), 2)
            try:
                self.marginLevelBeforeLastOpen = round(equity *
                                                       leverage / (1000 * self.totalPositionSizesDuringAprox[-2] * XXXYYY), 2)
            except ZeroDivisionError:
                self.marginLevelBeforeLastOpen = 100
            try:
                self.aproxRatio = round(
                    self.aproxDistanceForAverageOpeningPrice / (amountOfAprox * distOfAprox) * 100, 2)
            except ZeroDivisionError:
                self.aproxRatio = 0

        except AttributeError:
            print(
                "You must declare \"lot\" or \"maxDist\" variable.")
            print()


class SignalStrength:

    def __init__(self, client, supportResistanceALL, daySS, oneHourSS,  quaterSS, fiveSS,
                 oneSS, possibleCurrencyPairs, supportResistanceZoneSize, buyM1, buyM5, buyM15,
                 buyH1, buyD1,  sellM1, sellM5, sellM15, sellH1, sellD1, possibleTradesFromADX, blockedByCandle, isPriceInZone):
        buySignalStrength = {}
        sellSignalStrength = {}

        for pair in possibleCurrencyPairs:

            # spr sell
            sellStrength = 0
            if oneSS[pair] >= sellM1:
                sellStrength += 16
            if fiveSS[pair] >= sellM5:
                sellStrength += 16
            if quaterSS[pair] >= sellM15:
                sellStrength += 16
            if oneHourSS[pair] >= sellH1:
                sellStrength += 16
            if daySS[pair] >= sellD1:
                sellStrength += 16
            if isPriceInZone and sellStrength == 80:
                sellStrength += 20
            if possibleTradesFromADX[pair] == "buy" or blockedByCandle == True:
                sellStrength = 0
            sellSignalStrength[pair] = sellStrength

            # spr buy
            buyStrength = 0
            if oneSS[pair] <= buyM1:
                buyStrength += 16
            if fiveSS[pair] <= buyM5:
                buyStrength += 16
            if quaterSS[pair] <= buyM15:
                buyStrength += 16
            if oneHourSS[pair] <= buyH1:
                buyStrength += 16
            if daySS[pair] <= buyD1:
                buyStrength += 16
            if isPriceInZone and buyStrength == 80:
                buyStrength += 20
            if possibleTradesFromADX[pair] == "sell" or blockedByCandle == True:
                buyStrength = 0
            buySignalStrength[pair] = buyStrength

            self.buyStrength = str(buyStrength) + "%"
            self.sellStrength = str(sellStrength) + "%"
            self.sellSignalStrength = sellSignalStrength
            self.buySignalStrength = buySignalStrength


class NearestSupportZone:

    def __init__(self, supportResistanceALL, bidAsk, possibleCurrencyPairs, supportResistanceZoneSize, isJPYinPair=False):

        if isJPYinPair == True:
            pipValue = 0.01
        else:
            pipValue = 0.0001

        nearestSupportZone = {}

        for pair in possibleCurrencyPairs:

            searched = float(bidAsk.bidPrices[pair])

            differences = {support: round(math.fabs(float(support) - searched), 5)
                           for support in supportResistanceALL[pair]
                           }

            for diff in differences:
                if differences[diff] == min(differences.values()):
                    nearestSupportZone[pair] = str(str(diff) + " , odległość do BID: " +
                                                   str(round(min(differences.values()) / pipValue, 1)) + "pips")

                    if round(min(differences.values()) / pipValue, 1) <= truncate(supportResistanceZoneSize / 2, 1):
                        self.isPriceInZone = "TAK"
                    else:
                        self.isPriceInZone = "NIE"

        self.nearestSupportZone = nearestSupportZone


class AddPositionsDistances:

    def __init__(self, currentTrades, possibleTradesFromStoch):

        for pair in possibleTradesFromStoch:

            if possibleTradesFromStoch[pair] == "buy":
                buyTrades = {pair: "buy"
                             for pair in currentTrades.openedTradesOnlyPairs
                             if currentTrades.openedTradesOnlyPairs[pair] == "buy"
                             }

                self.highestBuyPair = {pair.split()[0]: currentTrades.openedTradesOpeningPrices[pair]
                                       for pair in currentTrades.openedTradesOpeningPrices
                                       if currentTrades.openedTradesOpeningPrices[pair] == max(currentTrades.openedTradesOpeningPrices.values())
                                       }
                self.amountOfCurrentBuyApproximations = len(buyTrades.keys())

            elif possibleTradesFromStoch[pair] == "sell":
                sellTrades = {pair: "sell"
                              for pair in currentTrades.openedTradesOnlyPairs
                              if currentTrades.openedTradesOnlyPairs[pair] == "sell"
                              }

                self.lowestSellPair = {pair.split()[0]: currentTrades.openedTradesOpeningPrices[pair]
                                       for pair in currentTrades.openedTradesOpeningPrices
                                       if currentTrades.openedTradesOpeningPrices[pair] == min(currentTrades.openedTradesOpeningPrices.values())
                                       }
                self.amountOfCurrentSellApproximations = len(sellTrades.keys())


class DataFrames:

    def __init__(self, pipValue, oneSS, fiveSS, quaterSS, oneHourSS, daySS, profitsData, bidAsk, tradeHistoryDataFrame, currentTradesData, currentAllTradesData, signalStrengthData, nearestSupportZoneData, adxData):

        # SLOW STOCH DATA FRAME
        columns = []
        stochs = []
        for pair in oneSS:
            stochs.append([oneSS[pair], fiveSS[pair],
                           quaterSS[pair], oneHourSS[pair], daySS[pair]])
            columns.append(pair)

        index = 0
        for stoch in stochs:
            if index == 0:
                slowStochDataFrame = pd.DataFrame(
                    data=stoch, index=["STOCH 1M", "STOCH 5M", "STOCH 15M", "STOCH H1", "STOCH D1"], columns=[columns[index]])
            else:
                slowStochDataFrame[columns[index]] = stoch
            index += 1
        slowStochDataFrame.columns.name = "SLOW STOCH"

        # PROFITS DATA FRAME
        profitsDataFrame = pd.DataFrame(data=profitsData, index=["WYNIK OBECNYCH POZYCJI", "CHWILOWE SALDO KONTA",
                                                                 "BALANS KONTA", "ZYSK DZIŚ", "STOPA ZWROTU DZIŚ", "ŚR. ZYSK Z POZ. DZIŚ", "ŚR.CZAS TRW. POZ. DZIŚ", "ILOŚĆ POZYCJI DZIŚ", "ZYSK [M-C]", "STOPA ZWROTU [M-C]",
                                                                 "ZYSK CAŁKOWITY", "STOPA ZWROTU CAŁK.", "ŚR. ZYSK DZIENNY [M-C]", "ŚR.CZAS TRW. POZ. [M-C]",
                                                                 "ŚR. IL. POZYCJI/DZIEŃ [M-C]", "ILOŚĆ POZYCJI [M-C]", "IL. PRZYBL. POZYCJI [M-C]",
                                                                 "% PRZYBL. POZYCJI [M-C]", "CZAS TRWANIA PĘTLI", "MARGIN LEVEL"], columns=["WARTOŚĆ"])

        # BID ASK DATA FRAME
        columns = []
        bidAsks = []
        for pair in bidAsk[0]:
            bidAsks.append([bidAsk[0][pair], bidAsk[1][pair],
                            bidAsk[2][pair], bidAsk[3], bidAsk[4], bidAsk[5], bidAsk[6], bidAsk[7]])
            columns.append(pair)

        index = 0
        for bidAskValue in bidAsks:
            if index == 0:
                bidAskDataFrame = pd.DataFrame(
                    data=bidAskValue, index=["CENY BID", "CENY ASK", "SPREADY", "H1 IMPULS LIMIT", "H1 HIGH-LOW", "H1 OPEN-CLOSE", "H1 % WYP. ŚWIECY", "IMPULS?"], columns=[columns[index]])
            else:
                bidAskDataFrame[columns[index]] = bidAskValue
            index += 1

        # CURRENT PARAMS DATA FRAME
        columns = []
        currentTradesParams = []
        draft = {}
        temp = []

        for pair in currentTradesData[3]:
            draft[pair] = {"buy": 0, "sell": 0}

        for pair in draft:
            for direction in draft[pair]:
                try:
                    temp.append(
                        str(round(currentTradesData[0][pair][direction], 5)))
                except:
                    temp.append(None)
                try:
                    temp.append(
                        str(round(currentTradesData[1][pair][direction], 5)))
                except:
                    temp.append(None)
                try:
                    temp.append(
                        str(round(currentTradesData[2][pair][direction], 5)))
                except:
                    temp.append(None)
                try:
                    temp.append(
                        str(round(currentTradesData[3][pair][direction], 2)))
                except:
                    temp.append(None)
                columns.append(str(pair) + "-" + str(direction))
                currentTradesParams.append(temp)
                temp = []

        if currentTradesParams != []:
            index = 0
            for valueList in currentTradesParams:
                if index == 0:
                    currentTradesDataFrame = pd.DataFrame(
                        data=valueList, index=["OBECNE ŚR. CENY OTWARCIA", "OBECNE ŚR. DYSTANSE DO OTWARCIA [pips]", "STOPLOSY OBECNYCH POZYCJI", "ŁĄCZNY WOLUMEN"], columns=[columns[index]])
                else:
                    currentTradesDataFrame[columns[index]] = valueList
                index += 1
        else:
            currentTradesDataFrame = []

        # CURRENT ALL TRADES DATA FRAME
        try:
            distancesToOpenBuy = {pair: round((bidAsk[1][pair.split()[0]] - currentAllTradesData[3][pair]) / pipValue, 1)
                                  for pair in currentAllTradesData[0]
                                  if currentAllTradesData[0][pair] == "buy"
                                  }
        except:
            distancesToOpenBuy = {}

        try:
            distancesToOpenSell = {pair: round((currentAllTradesData[3][pair] - bidAsk[0][pair.split()[0]]) / pipValue, 1)
                                   for pair in currentAllTradesData[0]
                                   if currentAllTradesData[0][pair] == "sell"
                                   }
        except:
            distancesToOpenSell = {}

        distancesToOpenAllTemp = {**distancesToOpenBuy, **distancesToOpenSell}
        distancesToOpenAllSorted = sorted(distancesToOpenAllTemp.keys())
        distancesToOpenAll = {pair: distancesToOpenAllTemp[pair]
                              for pair in distancesToOpenAllSorted
                              }

        currentAllTradesData.append(distancesToOpenAll)

        if currentAllTradesData != [{}, {}, {}, {}, {}]:
            currentAllTradesDataFrame = pd.DataFrame(data=currentAllTradesData, index=[
                "KIERUNKI OBECNYCH POZYCJI", "WOLUMEN", "WYNIKI OBECNYCH POZYCJI", "CENY OTWARCIA", "ODLEGŁOŚCI DO OPEN"], columns=list(currentAllTradesData[0].keys()))
        else:
            currentAllTradesDataFrame = []

        # SIGNAL STRENGTH DATA FRAME
        columns = []
        signals = []
        for pair in signalStrengthData[0]:
            signals.append([str(signalStrengthData[0][pair])+" %",
                            str(signalStrengthData[1][pair])+" %"])
            columns.append(pair)

        index = 0
        for signal in signals:
            if index == 0:
                signalStrengthDataFrame = pd.DataFrame(
                    data=signal, index=["BUY", "SELL"], columns=[columns[index]])
            else:
                signalStrengthDataFrame[columns[index]] = signal
            index += 1
        signalStrengthDataFrame.columns.name = "SIŁA SYGNAŁU"

        # NEAREST SUPPORT DATA FRAME

        nearestSupportZoneDataFrame = pd.DataFrame(data=nearestSupportZoneData, index=[
                                                   "NAJBLIŻSZY OPÓR", "CENA W STREFIE?"], columns=["WARTOŚĆ"])

        # ADX DATA
        columns = []
        adxs = []
        for pair in adxData[0]:
            adxs.append([adxData[0][pair], adxData[1][pair],
                         adxData[2][pair], adxData[3][pair]])
            columns.append(pair)

        index = 0
        for adx in adxs:
            if index == 0:
                adxDataFrame = pd.DataFrame(
                    data=adx, index=["ADX", "+DMI", "-DMI", "KIERUNEK"], columns=[columns[index]])
            else:
                adxDataFrame[columns[index]] = adx
            index += 1

        self.dataFrames = [profitsDataFrame, adxDataFrame, slowStochDataFrame, signalStrengthDataFrame, currentTradesDataFrame,
                           currentAllTradesDataFrame,  bidAskDataFrame,
                           nearestSupportZoneDataFrame,  tradeHistoryDataFrame]


def calcDX(A, B):
    if A > B and A > 0:
        return A
    else:
        return 0


def get_smoothed_list(listName, k, listLength):
    listReversed = list(reversed(listName))
    # print("listReversed", listReversed)
    listSmoothReversed = []
    for index in range(listLength):
        if index == 0:
            # print("series", pd.Series(data=listReversed[:k]))
            # print("series", pd.Series(data=listReversed[:k]).mean())
            listSmoothReversed.append(
                pd.Series(data=listReversed[:k]).mean())
            # print()
        else:
            # print("listSmoothReversed[-1]", listSmoothReversed[-1])
            # print("listReversed[index + k - 1]", listReversed[index + k - 1])
            listSmoothReversed.append(
                (listSmoothReversed[-1] * (k-1) + listReversed[index + k - 1]) / k)
    listSmooth = list(reversed(listSmoothReversed))
    return listSmooth


def calcLastDX(plusDMI, minusDMI):
    try:
        return math.fabs(plusDMI - minusDMI) / (plusDMI + minusDMI) * 100
    except:
        return 0


def get_average(list):
    return pd.Series(data=list).mean()


class ADX:

    def __init__(self, client, possibleCurrencyPairs, timeFrame, k, minTrendLevel, strongTrendLevel, veryStrongTrendLevel, minDistanceBetweenDMI, today, chart=None):

        self.ADXvalue = {}
        self.plusDMI = {}
        self.minusDMI = {}

        multipliers = {"day": 24, "fourhour": 4,
                       "hour": 1, "halfhour": 0.5, "quater": 0.25}

        for pair in possibleCurrencyPairs:
            if chart == None:

                if today == "sun" or (today == "mon"):
                    timeDiff = timedelta(
                        hours=k * 7 * multipliers[timeFrame] + 48 * multipliers[timeFrame])
                elif today == "tue":
                    timeDiff = timedelta(
                        hours=k * 7 * multipliers[timeFrame] + 24 * multipliers[timeFrame])

                else:
                    timeDiff = timedelta(hours=k * 7 * multipliers[timeFrame])

                startTimeChart = (
                    datetime.now() - timeDiff).strftime("%Y-%m-%d %H:%M:%S")
                chart = Chart(client, pair, timeFrame,
                              startTime=startTimeChart)
                chartListDays = chart.chartReady
                self.chartData = chartListDays
            else:
                chartListDays = chart
                self.chartData = chartListDays

            chartLength = len(chartListDays)
            firstSmoothedLength = len(chartListDays) - k
            secondSmoothedLength = len(chartListDays) - 2 * k

            lows = []
            highs = []
            closes = []

            for note in list(reversed(chartListDays)):
                lows.append(note["low"])
                highs.append(note["high"])
                closes.append(note["close"])

            # df = pd.DataFrame(data=chartListDays)
            # df.to_excel("plik2.xlsx", index=False)

            # OBLICZENIE TRUE RANGE
            TR = []
            for index in range(chartLength-1):
                TR.append(round(max([highs[index] - lows[index], lows[index] -
                                     closes[index+1], highs[index] - closes[index+1]]), 5))
            # OBLICZENIE ATR SMOOTH
            ATRsmooth = get_smoothed_list(TR, k, firstSmoothedLength)

            plusDX = []
            minusDX = []

            for index in range(chartLength-1):
                plusDX.append(
                    calcDX(highs[index] - highs[index + 1], lows[index+1] - lows[index]))
                minusDX.append(
                    calcDX(lows[index+1] - lows[index], highs[index] - highs[index + 1]))

            plusDXsmooth = get_smoothed_list(plusDX, k, firstSmoothedLength)
            minusDXsmooth = get_smoothed_list(minusDX, k, firstSmoothedLength)

            plusDMI = []
            minusDMI = []

            for index in range(firstSmoothedLength):
                plusDMI.append(plusDXsmooth[index] / ATRsmooth[index] * 100)
                minusDMI.append(minusDXsmooth[index] / ATRsmooth[index] * 100)

            DX = []
            for index in range(firstSmoothedLength):
                DX.append(calcLastDX(plusDMI[index], minusDMI[index]))

            ADXvalues = get_smoothed_list(DX, k, secondSmoothedLength+1)

            self.ADXvalue[pair] = round(ADXvalues[0], 2)
            self.plusDMI[pair] = round(plusDMI[0], 2)
            self.minusDMI[pair] = round(minusDMI[0], 2)
            self.possibleDirectionsFromAdx = {}

            for pair in possibleCurrencyPairs:
                if self.ADXvalue[pair] > minTrendLevel and \
                        self.plusDMI[pair] > minTrendLevel and \
                        self.plusDMI[pair] >= self.minusDMI[pair] + minDistanceBetweenDMI:
                    self.possibleDirectionsFromAdx[pair] = "buy"
                elif self.ADXvalue[pair] > minTrendLevel and \
                    self.minusDMI[pair] > minTrendLevel and \
                        self.minusDMI[pair] >= self.plusDMI[pair] + minDistanceBetweenDMI:
                    self.possibleDirectionsFromAdx[pair] = "sell"
                else:
                    self.possibleDirectionsFromAdx[pair] = "both"

                self.trendStrength = {}
                if self.possibleDirectionsFromAdx[pair] == "both":
                    self.trendStrength[pair] = "konsolidacja"
                elif self.possibleDirectionsFromAdx[pair] == "buy" and (self.ADXvalue[pair] > veryStrongTrendLevel and self.plusDMI[pair] > veryStrongTrendLevel):
                    self.trendStrength[pair] = "b.mocny trend wzrostowy"
                elif self.possibleDirectionsFromAdx[pair] == "buy" and (self.ADXvalue[pair] > strongTrendLevel and self.plusDMI[pair] > strongTrendLevel):
                    self.trendStrength[pair] = "mocny trend wzrostowy"
                elif self.possibleDirectionsFromAdx[pair] == "buy" and (self.ADXvalue[pair] > minTrendLevel and self.plusDMI[pair] > minTrendLevel):
                    self.trendStrength[pair] = "trend wzrostowy"
                elif self.possibleDirectionsFromAdx[pair] == "sell" and (self.ADXvalue[pair] > veryStrongTrendLevel and self.minusDMI[pair] > veryStrongTrendLevel):
                    self.trendStrength[pair] = "b.mocny trend spadkowy"
                elif self.possibleDirectionsFromAdx[pair] == "sell" and (self.ADXvalue[pair] > strongTrendLevel and self.minusDMI[pair] > strongTrendLevel):
                    self.trendStrength[pair] = "mocny trend spadkowy"
                elif self.possibleDirectionsFromAdx[pair] == "sell" and (self.ADXvalue[pair] > minTrendLevel and self.minusDMI[pair] > minTrendLevel):
                    self.trendStrength[pair] = "trend spadkowy"

            self.reversedADX = list(reversed(ADXvalues))
            self.reversedPlusDMI = list(reversed(plusDMI))
            self.reversedMinusDMI = list(reversed(minusDMI))


class EMA:

    def __init__(self, client, timeFrame, today, ma_slow, ma_medium, ma_fast, possibleCurrencyPairs):

        multipliers = {"day": 24, "fourhour": 4,
                       "hour": 1, "halfhour": 0.5, "quater": 0.25}

        if today == "sun" or (today == "mon"):
            timeDiff = timedelta(
                hours=ma_slow * 2 * multipliers[timeFrame] + 48 * multipliers[timeFrame])
        elif today == "tue":
            timeDiff = timedelta(
                hours=ma_slow * 2 * multipliers[timeFrame] + 24 * multipliers[timeFrame])
        else:
            timeDiff = timedelta(hours=ma_slow * 2 * multipliers[timeFrame])

        startTimeChart = (
            datetime.now() - timeDiff).strftime("%Y-%m-%d %H:%M:%S")
        chart = Chart(client, possibleCurrencyPairs[0], timeFrame,
                      startTime=startTimeChart)
        chartListDays = chart.chartReady

        chartReversed = list(reversed(chartListDays))

        closePrices = [note["close"]
                       for note in chartReversed
                       ]

        self.ema_averages = {}

        for parameter in [ma_slow, ma_medium, ma_fast]:

            multiplier = 2 / (parameter + 1)
            endPoint = parameter * (-1) - 1
            print(endPoint)

            average = np.average(closePrices[endPoint:-1])

            averages = [average]
            emaAverages = []

            for price in list(reversed(closePrices[0: endPoint])):
                emaAverages.append(
                    ((price - averages[-1]) * multiplier) + averages[-1])
                averages.append(
                    ((price - averages[-1]) * multiplier) + averages[-1])
            """
            sns.lineplot(data=pd.Series(
                data=list(reversed(closePrices[0: endPoint]))))
            sns.lineplot(data=pd.Series(data=emaAverages))
            plt.show()
            input("wykres")
            """

            self.ema_averages[parameter] = round(emaAverages[-1], 5)
