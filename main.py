from tradingDefs import *
from tradingMail import SendMessage

from pprint import pprint
from copy import deepcopy
from datetime import datetime

import json
import eventlet
import socket
import logging
import time
import ssl
from threading import Thread
import os
import math
import stdiomask
import numpy as np
import pandas as pd
import facebook
import requests
import discord
from discord import Webhook, RequestsWebhookAdapter, File
from dotenv import load_dotenv
from pathlib import Path


"""PARAMETRY
"""

tradedPair = "EURUSD"
currency1 = "EUR"
currency2 = "USD"
provisionRate = 0.2
mine_account = True

daysOfWeek = {0: "mon", 1: "tue", 2: "wed",
              3: "thu", 4: "fri", 5: "sat", 6: "sun"}


userId = 1111111
password = stdiomask.getpass(prompt="Hasło: ", mask="*")
gmail_account = "gmail_account@gmail.com"

facebookMode = False
accountType = "demo"

initialDeposit = 10000


"""POCZĄTEK PARAMETRÓW=====================
"""
# ↓ wartość skoku SL dla zabezpieczenia zysku [pips]
stopLossStep = 6
# ↓ dźwignia u brokera
leverage = 30
# ↓ czy w parze jest JEN. Wartość może być tylko "True" lub "False"
isJPYinPair = False

if isJPYinPair == True:
    pipValue = 0.01
else:
    pipValue = 0.0001

# ↓ ilość "przybliżeń ceny" - czyli ile razy chcemy dokładać do obecnego trejda
amountOfAprox = 2
# ↓ po ilu pipsach dokładamy do obecnych pozycji, aby je przybliżyć
distOfAprox = 300
firstMultiplier = None
allMultiplier = 0.3
lot = None
maxDist = 300
minMargin = 100
possibleCurrencyPairs = [tradedPair]
importantCurrencies = [currency1, currency2]
# wartości MAX slowstoch dla BUY
buyM1 = 20
buyM5 = 25
buyM15 = 25
buyH1 = 30
buyD1 = 50
# wartości MIN stoch dla SELL są odwrotnością BUY
sellM1 = 100 - buyM1
sellM5 = 100 - buyM5
sellM15 = 100 - buyM15
sellH1 = 100 - buyH1
sellD1 = 100 - buyD1


# odległość pomiędzy strefami support/resistance [pips]
supportResistanceZoneDistances = 50
# rozmiar strefy wsparcia/oporu w okolicy linii wsparcia/oporu w pipsach [supportResistanceZoneDistances / 4]
supportResistanceZoneSize = int(
    truncate(supportResistanceZoneDistances / 4, 0))

# parametry ADX
adxParameter = 14
minTrendLevel = 20
strongTrendLevel = 30
veryStrongTrendLevel = 40
minDistanceBetweenDMI = 2

# parametry średnich kroczących
ma_slow = 200
ma_medium = 100
ma_fast = 25

# parametry do obliczania impulsu
impuls_limit = 0.7


"""KONIEC PARAMETRÓW=======================================
"""
message = []
fileName = 0
iteration = 0
stopLosses = {}
previous = False
openedTradeMessage = ""
dataFrames = []
chartFileName = None
possibleTradesFromADX = {}
previousADX = False
nowTime = str(datetime.now().strftime("%H:%M"))
summaryVolumes = {}
client = None
temporaryEURPLN = 4.52


def check_list_for_pair(listName, pair, direction):
    try:
        return listName[pair][direction]
    except KeyError:
        return 0


def get_distance_between_open_and_now(bidAsk, averageOpeningPricesByDirection, pair, direction):
    try:
        if direction == "buy":
            return round((bidAsk.bidPrices[pair] - averageOpeningPricesByDirection[pair]["buy"]) * 10000, 1)
        elif direction == "sell":
            return round((averageOpeningPricesByDirection[pair]["sell"] - bidAsk.askPrices[pair]) * 10000, 1)
    except:
        return 0


def check_hedge_with_average_open_prices(bidAsk, averageOpeningPricesByDirection, direction, pair):
    try:
        if direction == "buy":
            if bidAsk.askPrices[pair.split()[0]] - averageOpeningPricesByDirection[pair.split()[0]]["sell"] <= pipValue * 5:
                return True
        elif direction == "sell":
            if averageOpeningPricesByDirection[pair.split()[0]]["buy"] - bidAsk.bidPrices[pair.split()[0]] <= pipValue * 5:
                return True
    except KeyError:
        return False


"""WCZYTANIE WSPARĆ I OPORÓW
"""

supportResistanceALL = {}
for pair in possibleCurrencyPairs:
    supportResistanceALL[pair] = list(
        np.arange(0, 2, (pipValue * supportResistanceZoneDistances)).round(5))

while True:

    print(str(userId) + " " + accountType)

    if message == []:
        pass
    else:
        if facebookMode == True:
            pass
        else:
            SendMessage(gmail_account, str(
                fileName) + " | " + str(userId) + " | " + tradedPair + " | " + accountType, str(message), file=chartFileName, dataFrames=dataFrames)

    try:
        today = daysOfWeek[datetime.today().weekday()]

        if today == "sat" or (today == "sun" and str(datetime.now().strftime("%H%M")) <= "2300") or (today == "fri" and str(datetime.now().strftime("%H%M")) >= "2159"):
            print("czekam...")
            time.sleep(60)
            continue

        else:

            print("supportResistanceALL", supportResistanceALL)

            # logger properties
            FORMAT = '[%(asctime)-15s][%(funcName)s:%(lineno)d] %(message)s'
            logging.basicConfig(format=FORMAT, level=logging.DEBUG,
                                filename='error_logs.log')

            if client == None:

                client = APIClient(accType=accountType)

                loginResponse = client.execute(
                    loginCommand(userId=userId, password=password))

                if(loginResponse['status'] == False):
                    print('Login failed. Error code: {0}'.format(
                        loginResponse['errorCode']))

            endTime = datetime.now().strftime("%H")

            startCounter = time.perf_counter()

            today = daysOfWeek[datetime.today().weekday()]

            # sprawdzenie czy zmieniła się godzina - do LOGA
            startTime = datetime.now().strftime("%H")
            if startTime != endTime:
                hourChange = 1
            else:
                hourChange = 0

            currentTrades = CurrentTrades(client)
            accountData = MoneyManagement(client)
            print("currentTrades", currentTrades.openedTradesOnlyPairs)

            transactionsToKill = []

            """ AWARYJNE SPRAWDZENIE CZY CENY NIE OMINĘŁY STOPLOSSÓW I TAKEPROFITÓW
            """

            # sprawdzenie czy ceny nie ominęły stoplossów i takeprofitów

            if currentTrades.openedTradesOnlyPairs != {}:
                bidAsk = BidAsk(
                    client, possibleCurrencyPairs)

            for pair in currentTrades.openedTradesOnlyPairs:
                try:
                    if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                        if pair in currentTrades.openedTradesStopLoss and bidAsk.bidPrices[pair] < currentTrades.openedTradesStopLoss[pair] and currentTrades.openedTradesStopLoss[pair] != 0:
                            transactionsToKill.append(pair)

                    elif currentTrades.openedTradesOnlyPairs[pair] == "sell":
                        if pair in currentTrades.openedTradesStopLoss and bidAsk.askPrices[pair] > currentTrades.openedTradesStopLoss[pair] and currentTrades.openedTradesStopLoss[pair] != 0:
                            transactionsToKill.append(pair)
                except KeyError:
                    pass

            """ AWARYJNE SPRAWDZENIE POZIOMU STOP OUT
            """

            if accountData.marginLevel < 50 and currentTrades.openedTradesOnlyPairs != {}:
                # ustalenie najbardziej stratnej pozycji
                positionWithBiggestLoss = {v: k for k, v in currentTrades.openedTradesResults.items()}[
                    min(list(currentTrades.openedTradesResults.values()))]
                transactionsToKill.append(positionWithBiggestLoss)

            """ ZAMKNIĘCIE TRANSAKCJI Z LISTY transactionsToKill
            """
            # zamknięcie transakcji, z listy transactionsToKill
            if len(transactionsToKill) > 0:
                currentTrades.close_trades(client, transactionsToKill)

            """OBLICZENIE UŚREDNIONYCH POZIOMÓW OPEN
            """
            averageOpeningPricesByDirection = {}

            if currentTrades.openedTradesOnlyPairs != {}:

                addPositionObject = AddPosition(
                    accountData, currentTrades, bidAsk)

                summaryVolumes = addPositionObject.summaryVolumes
                smallestVolumes = addPositionObject.smallestVolumes

                pairsByDirections = {"buy": [], "sell": []}
                for pair in currentTrades.openedTradesOnlyPairs:
                    if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                        pairsByDirections["buy"].append(pair)
                    elif currentTrades.openedTradesOnlyPairs[pair] == "sell":
                        pairsByDirections["sell"].append(pair)

                openingPricesTimesVolumesByDirection = {direction: [currentTrades.openedTradesOpeningPrices[pair] * currentTrades.openedTradesVolumes[pair]
                                                                    for pair in pairsByDirections[direction]
                                                                    ]
                                                        for direction in pairsByDirections}

                averageOpeningPricesByDirection = {pair:  {direction: round(sum(openingPricesTimesVolumesByDirection[direction]) / (summaryVolumes[pair][direction]), 5)
                                                           for direction in openingPricesTimesVolumesByDirection
                                                           if summaryVolumes[pair][direction] > 0}
                                                   for pair in summaryVolumes}

                print("averageOpeningPricesByDirection",
                      averageOpeningPricesByDirection)
                print("currentTrades.openedTradesOpeningPrices",
                      currentTrades.openedTradesOpeningPrices)

            """ AKTUALIZOWANIE TRAILIG PROFIT DLA AKTUALNYCH TREJDÓW
            """

            stopLossesBuy = {pair.split()[0]: {currentTrades.openedTradesOnlyPairs[pair]: currentTrades.openedTradesStopLoss[pair]}
                             for pair in currentTrades.openedTradesOnlyPairs
                             if currentTrades.openedTradesOnlyPairs[pair] == "buy"
                             }

            stopLossesSell = {pair.split()[0]: {currentTrades.openedTradesOnlyPairs[pair]: currentTrades.openedTradesStopLoss[pair]}
                              for pair in currentTrades.openedTradesOnlyPairs
                              if currentTrades.openedTradesOnlyPairs[pair] == "sell"
                              }

            stopLosses = {pair.split()[0]: {"buy": check_list_for_pair(stopLossesBuy, pair.split()[0], "buy"), "sell": check_list_for_pair(stopLossesSell, pair.split()[0], "sell")}
                          for pair in currentTrades.openedTradesOnlyPairs
                          }

            print("stopLosses", stopLosses)

            trailingStoploss = TrailingStopLoss()

            if len(list(currentTrades.openedTradesOnlyPairs.keys())) > 0:
                # sprawdzenie czy można zaktualizować stop lossy i jeśli tak, obliczenie ich
                stopLossesToUpdate = trailingStoploss.update_stop_loss(
                    client,  currentTrades, averageOpeningPricesByDirection, stopLosses, stopLossStep, isJPYinPair=isJPYinPair)

                # zaktualizowanie stop lossów
                if len(list(stopLossesToUpdate.keys())) > 0:
                    trailingStoploss.execute_update_stoploss(
                        client, currentTrades, stopLossesToUpdate)

            """ SPRAWDZENIE ZAKRESÓW OBECNEJ ŚWIECY I OBLICZENIE possibleTradesFromStoch
            """

            candleRange = CandleRange(client, "hour", tradedPair, isJPYinPair)
            lastCandleRange = candleRange.lastCandleRange
            lastCandleTrueRange = candleRange.lastCandleTrueRange
            chartCandleRange = candleRange.chartCandleRange
            lastCandleDirection = candleRange.candleDirection
            averageCandleRange = candleRange.averageCandleRange
            averageImpulsRange = candleRange.averageImpulsRange
            print("averageCandleRange", averageCandleRange)
            print("averageImpulsRange", averageImpulsRange)
            print("lastCandleDirection", lastCandleDirection)
            print("lastCandleRange", lastCandleRange)
            print("lastCandleTrueRange", lastCandleTrueRange)
            print("%", round(lastCandleTrueRange / lastCandleRange, 2))

            """ADX
            """

            endTimeADX = str(datetime.now().strftime("%M"))
            nowTimeADX = str(datetime.now().strftime("%H:%M"))
            if previousADX == False:
                previousADX == endTimeADX

            adxTimes = ["04", "09", "14", "19", "24",
                        "29", "34", "39", "44", "49", "54", "59"]

            if (previousADX != endTimeADX and endTimeADX in adxTimes) or possibleTradesFromADX == {}:
                print("OBLICZANIE ADX")

            adx = ADX(client, possibleCurrencyPairs,
                      "hour", adxParameter, minTrendLevel, strongTrendLevel, veryStrongTrendLevel, minDistanceBetweenDMI, today, chart=chartCandleRange)

            ADXvalue = adx.ADXvalue
            minusDMI = adx.minusDMI
            plusDMI = adx.plusDMI
            possibleTradesFromADX = adx.possibleDirectionsFromAdx

            trendStrength = adx.trendStrength
            previousADX = endTimeADX

            print("ADXvalue", ADXvalue)
            print("plusDMI", plusDMI)
            print("minusDMI", minusDMI)
            print("possibleTradesFromADX", possibleTradesFromADX)

            """  WARTOŚCI SLOW STOCH
            """

            # obliczenie slow stoch dla możliwych trejdów
            slowStochOne = SlowStoch(
                client, possibleCurrencyPairs, "one", today=today)
            print("slowStochOne",
                  slowStochOne.possibleTradesSlowStoch)
            slowStochFive = SlowStoch(
                client, possibleCurrencyPairs, "five", today=today)
            print("slowStochFive",
                  slowStochFive.possibleTradesSlowStoch)
            # time.sleep(1)
            slowStochQuater = SlowStoch(
                client, possibleCurrencyPairs, "quater", today=today)
            print("slowStochQuater", slowStochQuater.possibleTradesSlowStoch)
            # time.sleep(1)
            slowStochOneHour = SlowStoch(
                client, possibleCurrencyPairs, "hour", chart=chartCandleRange, today=today)
            print("slowStochOneHour", slowStochOneHour.possibleTradesSlowStoch)

            slowStochDay = SlowStoch(
                client, possibleCurrencyPairs, "day", today=today)
            print("slowStochDay", slowStochDay.possibleTradesSlowStoch)

            # time.sleep(1)

            # możliwe sell i buy z slowstocha
            possibleTradesFromStoch = SlowStoch.get_possible_trades_from_stoch(possibleCurrencyPairs,
                                                                               slowStochDay.possibleTradesSlowStoch,
                                                                               slowStochOneHour.possibleTradesSlowStoch,
                                                                               slowStochQuater.possibleTradesSlowStoch,
                                                                               slowStochFive.possibleTradesSlowStoch,
                                                                               slowStochOne.possibleTradesSlowStoch,
                                                                               buyM1, buyM5, buyM15, buyH1, buyD1, sellM1, sellM5, sellM15, sellH1, sellD1,
                                                                               possibleTradesFromADX, ADXvalue, minusDMI, plusDMI, strongTrendLevel, veryStrongTrendLevel
                                                                               )
            blockedByCandle = False

            # sprawdzenie zakresu obecnej świecy i wyczyśzczenie possibleTradesFromStoch jeśli świeca jest impulsem
            if (lastCandleTrueRange >= averageImpulsRange and possibleTradesFromStoch != {}) or \
                    (lastCandleRange >= averageImpulsRange and lastCandleTrueRange / lastCandleRange >= impuls_limit and possibleTradesFromStoch != {}):
                if possibleTradesFromStoch[tradedPair] == "buy" and lastCandleDirection == "up":
                    pass
                elif possibleTradesFromStoch[tradedPair] == "sell" and lastCandleDirection == "down":
                    pass
                else:
                    possibleTradesFromStoch = {}
                    blockedByCandle = True

            print("possibleTradesFromStoch", possibleTradesFromStoch)

            if possibleTradesFromStoch != {}:

                tradeProximityCheck = TradeProximity(
                    client, supportResistanceALL, possibleTradesFromStoch, supportResistanceZoneSize, possibleCurrencyPairs=possibleCurrencyPairs, isJPYinPair=isJPYinPair)

                tradesWithOkProximityAndStoch = tradeProximityCheck.tradesWithOkProximityAndStoch

            else:
                tradesWithOkProximityAndStoch = {}

            """ SPRAWDZENIE tradesWithOkProximityAndStoch z ADX
            """

            possibleTradesWithAllOk = {}

            for pair in tradesWithOkProximityAndStoch:
                if tradesWithOkProximityAndStoch[pair] == possibleTradesFromADX[pair] or possibleTradesFromADX[pair] == "both":
                    possibleTradesWithAllOk[pair] = tradesWithOkProximityAndStoch[pair]

            print("possibleTradesWithAllOk",
                  possibleTradesWithAllOk)

            """  USUNIĘCIE Z MOŻLIWYCH TREJDÓW PAR WALUT OBECNIE HANDLOWANYCH I POWTARZAJĄCYCH SIE
            """

            # ponowne pobranie obecnych transakcji
            # time.sleep(1)
            currentTrades = CurrentTrades(client)

            currentDirections = Hedge.check_hedge_with_current_trades_for_duplicates(
                currentTrades.openedTradesOnlyPairs)

            if possibleTradesWithAllOk == {}:
                pass
            else:
                bidAsk = BidAsk(client, possibleCurrencyPairs)
                try:
                    currencyExchangePLN = FreeCurrencyConverter.get_PLN_exchange_rate(
                        possibleCurrencyPairs)
                except:
                    currencyExchangePLN = {tradedPair: temporaryEURPLN}
                print("currencyExchangePLN", currencyExchangePLN)
                lastPair = list(possibleTradesWithAllOk.keys())[-1]

            if currentTrades.openedTradesOnlyPairs == {}:

                for pair in possibleTradesWithAllOk:
                    try:
                        currentDirectionsLen = len(
                            set(currentDirections[pair.split()[0]]))
                    except KeyError:
                        currentDirectionsLen = 0

                    if currentDirectionsLen == 2:
                        pass
                    else:

                        """OBLICZANIE POZYCJI DLA possibleTradesWithAllOk I OTWARCIE TREJDÓW
                        """

                        # przed obliczeniem pozycji najpierw trzeba pobrać kurs XX/PLN

                        if possibleTradesWithAllOk[pair] == "buy":
                            simulation = Simulation(accountData.equity, bidAsk.askPrices[pair], amountOfAprox, distOfAprox,
                                                    currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)
                        elif possibleTradesWithAllOk[pair] == "sell":
                            simulation = Simulation(accountData.equity, bidAsk.bidPrices[pair], amountOfAprox, distOfAprox,
                                                    currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)

                        print("- Odległość do STOP OUT względem pierwszej pozycji po zastosowaniu przybliżeń: ",
                              int(truncate(simulation.stopOutDistanceAfterAprox, 0)))

                        openedTradeMessage = "- Odległość do STOP OUT względem pierwszej pozycji po zastosowaniu przybliżeń: " + str(truncate(simulation.stopOutDistanceAfterAprox, 0)) + "\n" + \
                            "- O ile przesunie się uśredniony trejd: " + str(simulation.aproxDistanceForAverageOpeningPrice) + "\n" + \
                            "- Wielkości kolejno otwieranych pozycji: " + str(simulation.positionSizes) + "\n" + \
                            "- Łączna wielkość przybliżanej pozycji po każdym przybliżeniu: " + \
                            str(simulation.totalPositionSizesDuringAprox)

                        print("currencyExchangePLN", currencyExchangePLN)

                        # OBLICZANIE pozycji dla OkTradów
                        positionsParameters = PositionParameters(client, possibleTradesWithAllOk, currencyExchangePLN,
                                                                 accountData.equity,  currentTrades, summaryVolumes, simulation=simulation)

                        # otwarcie OK trejdów
                        positionsParameters.execute_trades(client)

                        if pair == lastPair:
                            # ponowne pobranie current trades
                            currentTrades = CurrentTrades(client)

                            """OBLICZENIE UŚREDNIONYCH POZIOMÓW OPEN
                            """
                            averageOpeningPricesByDirection = {}

                            if currentTrades.openedTradesOnlyPairs != {}:

                                summaryVolumesByDirection = AddPosition(
                                    accountData, currentTrades, bidAsk).summaryVolumes

                                pairsByDirections = {"buy": [], "sell": []}
                                for pair in currentTrades.openedTradesOnlyPairs:
                                    if currentTrades.openedTradesOnlyPairs[pair] == "buy":
                                        pairsByDirections["buy"].append(pair)
                                    elif currentTrades.openedTradesOnlyPairs[pair] == "sell":
                                        pairsByDirections["sell"].append(pair)

                                openingPricesTimesVolumesByDirection = {direction: [currentTrades.openedTradesOpeningPrices[pair] * currentTrades.openedTradesVolumes[pair]
                                                                                    for pair in pairsByDirections[direction]
                                                                                    ]
                                                                        for direction in pairsByDirections}

                                averageOpeningPricesByDirection = {pair:  {direction: round(sum(openingPricesTimesVolumesByDirection[direction]) / (summaryVolumesByDirection[pair][direction]), 5)
                                                                           for direction in openingPricesTimesVolumesByDirection
                                                                           if summaryVolumesByDirection[pair][direction] > 0}
                                                                   for pair in summaryVolumesByDirection}

                                print("averageOpeningPricesByDirection",
                                      averageOpeningPricesByDirection)
                                print("currentTrades.openedTradesOpeningPrices",
                                      currentTrades.openedTradesOpeningPrices)
            else:
                print("Already trading.. only Hedge and Double")

            """HEDGE
            """

            if currentTrades.openedTradesOnlyPairs != {} and possibleTradesWithAllOk != {}:

                currentTrades = CurrentTrades(client)
                hedgeDirections = Hedge.reverse_directions_for_hedge(
                    currentTrades.openedTradesOnlyPairs)
                print("hedgeDirections", hedgeDirections)

                currentDirections = Hedge.check_hedge_with_current_trades_for_duplicates(
                    currentTrades.openedTradesOnlyPairs)
                print("currentDirections", currentDirections)

                if hedgeDirections == {}:
                    pass
                else:
                    bidAsk = BidAsk(client, hedgeDirections)

                for pair in hedgeDirections:

                    print("ilość obecnych kierunków", len(
                        set(currentDirections[pair.split()[0]])))

                    if len(set(currentDirections[pair.split()[0]])) >= 2 or check_hedge_with_average_open_prices(bidAsk, averageOpeningPricesByDirection, hedgeDirections[pair], pair):
                        print("POMINIETO HEDGE")

                    else:

                        if pair.split()[0] in possibleTradesWithAllOk and possibleTradesWithAllOk[pair.split()[0]] == hedgeDirections[pair]:

                            possibleHedgesWithAllOk = possibleTradesWithAllOk

                            print("possibleHedgesWithAllOk",
                                  possibleHedgesWithAllOk)

                            try:
                                if possibleHedgesWithAllOk[pair] == "buy":
                                    simulation = Simulation(accountData.equity, bidAsk.askPrices[pair], amountOfAprox, distOfAprox,
                                                            currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)

                                elif possibleHedgesWithAllOk[pair] == "sell":
                                    simulation = Simulation(accountData.equity, bidAsk.bidPrices[pair], amountOfAprox, distOfAprox,
                                                            currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)

                                hedge = PositionParameters(client, possibleHedgesWithAllOk, currencyExchangePLN,
                                                           accountData.equity, currentTrades, smallestVolumes, simulation=simulation, hedge=True)

                                hedge.execute_trades(client)

                            except KeyError:
                                pass

                        else:
                            print("Niezgodność stocha z hedge")
            else:
                print("Brak possibleTradesWithAllOk aby otworzyć hedge")

            """PODWAJANIE POZYCJI
            """
            currentTrades = CurrentTrades(client)

            if currentTrades.openedTradesOnlyPairs != {} and possibleTradesWithAllOk != {}:

                bidAsk = BidAsk(client, possibleCurrencyPairs)

                currentVolumeForMargin = AddPosition(
                    accountData, currentTrades, bidAsk).maxVolume
                summaryVolumes = AddPosition(
                    accountData, currentTrades, bidAsk).summaryVolumes

                if accountData.marginLevel > minMargin:

                    for pair in possibleTradesWithAllOk:

                        for direction in averageOpeningPricesByDirection[pair]:

                            if direction == "buy" and possibleTradesWithAllOk[pair] == "buy":

                                addPositionsDistances = AddPositionsDistances(
                                    currentTrades, possibleTradesWithAllOk)

                                priceDiff = round(addPositionsDistances.highestBuyPair[pair] -
                                                  bidAsk.askPrices[pair], 5)

                                minPriceDiff = round(addPositionsDistances.amountOfCurrentBuyApproximations *
                                                     distOfAprox * pipValue, 5)

                                if priceDiff >= minPriceDiff:  # >=
                                    possibleVolume = truncate(
                                        summaryVolumes[pair]["buy"] * allMultiplier, 2)

                                    marginLevelAfterTrade = round((accountData.equity * 30) /
                                                                  (1000 * (summaryVolumes[pair.split()[0]]["buy"] +
                                                                           possibleVolume) * currencyExchangePLN[pair.split()[0]]), 2)

                                    if marginLevelAfterTrade >= minMargin:

                                        try:

                                            if possibleTradesWithAllOk[pair] == "buy":
                                                simulation = Simulation(accountData.equity, bidAsk.askPrices[pair], amountOfAprox, distOfAprox,
                                                                        currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)

                                            if possibleTradesWithAllOk[pair.split()[0]] == "buy":
                                                positionsParameters = PositionParameters(client, {pair.split()[0]: "buy"}, currencyExchangePLN,
                                                                                         accountData.equity, currentTrades, summaryVolumes, volume=possibleVolume, simulation=simulation)
                                                # otwarcie OK trejdów
                                                positionsParameters.execute_trades(
                                                    client)

                                        except KeyError:
                                            print(
                                                "Cena nie jest w strefie wsparcia/oporu")
                                            pass

                            elif direction == "sell" and possibleTradesWithAllOk[pair] == "sell":

                                addPositionsDistances = AddPositionsDistances(
                                    currentTrades, possibleTradesWithAllOk)

                                priceDiff = round(
                                    bidAsk.bidPrices[pair] - addPositionsDistances.lowestSellPair[pair], 5)

                                minPriceDiff = round(addPositionsDistances.amountOfCurrentSellApproximations *
                                                     distOfAprox * pipValue, 5)

                                if priceDiff >= minPriceDiff and possibleTradesWithAllOk[pair] == "sell":

                                    possibleVolume = truncate(
                                        summaryVolumes[pair]["sell"] * allMultiplier, 2)

                                    marginLevelAfterTrade = round((accountData.equity * 30) /
                                                                  (1000 * (summaryVolumes[pair.split()[0]]["sell"] +
                                                                           possibleVolume) * currencyExchangePLN[pair.split()[0]]), 2)

                                    if marginLevelAfterTrade >= minMargin:

                                        try:
                                            if possibleTradesWithAllOk[pair] == "sell":
                                                simulation = Simulation(accountData.equity, bidAsk.bidPrices[pair], amountOfAprox, distOfAprox,
                                                                        currencyExchangePLN[pair], leverage, firstMultiplier, allMultiplier, isJPYinPair, maxDist, lot)

                                            if possibleTradesWithAllOk[pair.split()[0]] == "sell":
                                                positionsParameters = PositionParameters(client, {pair.split()[0]: "sell"}, currencyExchangePLN,
                                                                                         accountData.equity, currentTrades, summaryVolumes, volume=possibleVolume, simulation=simulation)
                                                # otwarcie OK trejdów
                                                positionsParameters.execute_trades(
                                                    client)

                                        except KeyError:
                                            print(
                                                "Cena nie jest w strefie wsparcia/oporu")
                                            pass

            else:
                print("Pominięto podwajanie")

            """ZAPISANIE LOGA, WYSŁANIE MAILA / PUBLIKACJA NA FB
            """
            endCounter = time.perf_counter()
            # loopTime = str(math.floor((endCounter - startCounter) / 60)) + ":" + str(round((endCounter - startCounter) % 60))
            loopTime = truncate(endCounter - startCounter, 5)
            print("loopTime", loopTime)

            endTime = str(datetime.now().strftime("%M"))
            nowTime = str(datetime.now().strftime("%H:%M"))
            if previous == False:
                previous == endTime

            if endTime != previous and (endTime == "30" or endTime == "00" or endTime == "45" or endTime == "15"):

                if lastCandleTrueRange >= averageImpulsRange or \
                        (lastCandleRange >= averageImpulsRange and lastCandleTrueRange / lastCandleRange >= impuls_limit):
                    impuls = "TAK"
                else:
                    impuls = "NIE"

                currentTrades = CurrentTrades(client)

                totalResult = 0
                for pair in currentTrades.openedTradesResults:
                    totalResult += currentTrades.openedTradesResults[pair]
                bidAsk = BidAsk(client, possibleCurrencyPairs)

                previous = endTime

                fileName = str(
                    datetime.now().strftime("%H:%M | %d.%m.%Y"))

                currentDistanceToTradeAverageOpenPrice = {pair: {"buy": get_distance_between_open_and_now(bidAsk, averageOpeningPricesByDirection, pair, "buy"), "sell": get_distance_between_open_and_now(bidAsk, averageOpeningPricesByDirection, pair, "sell")}
                                                          for pair in averageOpeningPricesByDirection
                                                          }
                spreads = {}
                for pair in bidAsk.spreads:
                    spreads[pair] = str(round(bidAsk.spreads[pair] * 10000, 1))

                tradeHistory = TradeHistory(
                    client, nowTime, today, facebookMode, isJPYinPair=isJPYinPair)

                if mine_account == False:
                    if today == "fri":
                        depositWithdrawalsHour = "21:45"
                    else:
                        depositWithdrawalsHour = "23:45"

                    if nowTime == depositWithdrawalsHour:
                        depositWithdrawals = DepositWithdrawals(
                            client, initialDeposit, accountData.balance, provisionRate, userId)

                if today == "fri" and nowTime == "21:45" or today != "fri" and nowTime == "23:45":
                    if tradeHistory.monthProfit == 0:
                        chartFileName = None
                    else:
                        chartFileName = ["profits_by_days.jpg",
                                         "duration_by_days.jpg"]
                        chartFileName = None
                else:
                    chartFileName = None

                # NAJBLIŻSZA STREFA WSPARCIA/OPORU
                nearestSupportZoneClass = NearestSupportZone(
                    supportResistanceALL, bidAsk, possibleCurrencyPairs, supportResistanceZoneSize, isJPYinPair=isJPYinPair)

                nearestSupportZone = nearestSupportZoneClass.nearestSupportZone

                isPriceInZone = nearestSupportZoneClass.isPriceInZone

                # SIŁA SYGNAŁU
                signalStrength = SignalStrength(client, supportResistanceALL, slowStochDay.possibleTradesSlowStoch, slowStochOneHour.possibleTradesSlowStoch,
                                                slowStochQuater.possibleTradesSlowStoch,
                                                slowStochFive.possibleTradesSlowStoch,
                                                slowStochOne.possibleTradesSlowStoch, possibleCurrencyPairs, supportResistanceZoneSize,
                                                buyM1, buyM5, buyM15, buyH1, buyD1, sellM1, sellM5, sellM15, sellH1, sellD1, possibleTradesFromADX, blockedByCandle, isPriceInZone)

                if currentTrades.openedTradesOnlyPairs == {}:
                    summaryVolumes = {}
                else:
                    summaryVolumes = AddPosition(
                        accountData, currentTrades, bidAsk).summaryVolumes

                if facebookMode == True:
                    pass
                else:

                    message = str(openedTradeMessage)

                    try:
                        percentOfAproxedPos = str(
                            round(tradeHistory.amountOfDouble / tradeHistory.amountOfTrades * 100, 2)) + "%"
                    except ZeroDivisionError:
                        percentOfAproxedPos = "0 %"

                    dataFrames = DataFrames(pipValue, slowStochOne.possibleTradesSlowStoch, slowStochFive.possibleTradesSlowStoch,
                                            slowStochQuater.possibleTradesSlowStoch, slowStochOneHour.possibleTradesSlowStoch, slowStochDay.possibleTradesSlowStoch,
                                            profitsData=[str(round(totalResult, 2)) + " PLN", str(accountData.equity) + " PLN", str(accountData.balance) + " PLN",
                                                         str(tradeHistory.todayProfit) + " PLN",   str(round(tradeHistory.todayProfit / (
                                                             accountData.balance - tradeHistory.todayProfit) * 100, 2)) + " %",
                                                         str(round(tradeHistory.todayAverageProfit, 2)) + " PLN", tradeHistory.averageTodayTradeTime, tradeHistory.todayNumberOfPositions, str(
                                                tradeHistory.monthProfit) + " PLN", str(round(tradeHistory.monthProfit / (accountData.balance - tradeHistory.monthProfit) * 100, 2)) + " %", str(round(accountData.balance - initialDeposit, 2)) + " PLN",
                                                str(round((accountData.balance - initialDeposit) /
                                                          initialDeposit * 100, 2)) + " %", tradeHistory.averageDailyProfit,
                                                tradeHistory.averageMonthTradeTime, tradeHistory.averageNumberOfPositionsPerDay, tradeHistory.amountOfTrades, tradeHistory.amountOfDouble, percentOfAproxedPos, str(loopTime), str(accountData.marginLevel) + "%"],
                                            bidAsk=[bidAsk.bidPrices,
                                                    bidAsk.askPrices, spreads, averageImpulsRange, lastCandleRange, lastCandleTrueRange, str(round(lastCandleTrueRange / lastCandleRange * 100, 2)) + "%", impuls],
                                            tradeHistoryDataFrame=tradeHistory.tradeHistoryDataFrame,
                                            currentTradesData=[
                                                averageOpeningPricesByDirection, currentDistanceToTradeAverageOpenPrice, stopLosses, summaryVolumes],
                                            currentAllTradesData=[
                                                currentTrades.openedTradesOnlyPairs, currentTrades.openedTradesVolumes, currentTrades.openedTradesResults, currentTrades.openedTradesOpeningPrices],
                                            signalStrengthData=[
                                                signalStrength.buySignalStrength, signalStrength.sellSignalStrength],
                                            nearestSupportZoneData=[
                                                str(nearestSupportZone[tradedPair]), str(isPriceInZone)],
                                            adxData=[ADXvalue, plusDMI, minusDMI, trendStrength]).dataFrames

                openedTradeMessage = ""

            else:
                message = []
            # client.disconnect()
            time.sleep(0.2)
            continue

    except:
        logging.exception("UPS: ")
        message = "Przerwana pętla"
        dataFrames = []
        client.disconnect()
        client = None
        time.sleep(5)
        continue
