#!/usr/bin/env python

#############################################################################
##
## Copyright (C) 2021 Joe Skaife.
## All rights reserved.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
#############################################################################

import csv
import sqlite3
import os
import requests
import glob
import _thread
import time

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from functools import partial
from enum import IntEnum

class SortEnum(IntEnum):
    SORT_STOCK_DOWN = 1
    SORT_PRICE_UP = 2
    SORT_IN_STOCK_PRICE_UP = 3
    
class DbRowEnum(IntEnum):
    DB_ROW_LCSC_PART = 0
    DB_ROW_FIRST_CAT = 1
    DB_ROW_SEC_CAT = 2
    DB_ROW_MFR_PART = 3
    DB_ROW_PACKAGE = 4
    DB_ROW_SOLDER_JNT = 5
    DB_ROW_MANF = 6
    DB_ROW_LIB_TYPE = 7
    DB_ROW_DESCR = 8
    DB_ROW_DATASHEET = 9
    DB_ROW_PRICE = 10
    DB_ROW_STOCK = 11
    DB_ROW_WORST_PRICE = 12
    DB_ROW_IMAGE = 13

class TableColumnEnum(IntEnum):
    TABLE_COL_PART = 0
    TABLE_COL_EXT = 1
    TABLE_COL_DESC = 2
    TABLE_COL_PKG = 3
    TABLE_COL_MANF = 4
    TABLE_COL_PRICE = 5
    TABLE_COL_STOCK = 6
    TABLE_COL_IMAGE = 7
    TABLE_COL_COUNT = 8

imageCacheDir = 'imageCache/'
failedPartsFile = imageCacheDir +'failedParts.txt'
defaultImage = 'no_image.png'
defaultDbFile = 'jlc.db'
                 
def getImage(imgUrl, lcscCode):
    try:
        response = requests.get(imgUrl, timeout=3.05)
        if response.status_code == 200:
            file = open(imageCacheDir + lcscCode + '.jpg', 'wb')
            file.write(response.content)
            file.close()
            return True
        else:
            return False
    except BaseException as err:
        print("Unexpected {err=}, {type(err)=}")        
        print('html request threw exception.')
        return False
        
def getImageFilename(datasheet, lcscPart):
    if datasheet.strip() == '':
        # No datasheet, no way to derive an image url
        imageFilename = defaultImage
    else:
        imageFilename = lcscPart + '.jpg'
        try:
            splitDatasheet = datasheet.split('_', 1)
            splitDatasheet = splitDatasheet[1].rsplit('.', 1)
        
            '''
             There are a number of variations of the url for the image - some of which look like typos
             All are based on the datasheet name (for want of a better algorithm)
            '''
            imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_front.jpg'
            
            if not getImage(imageLink, lcscPart):
                imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_front_10.jpg'

                if not getImage(imageLink, lcscPart):
                    imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_front_10.JPG'

                    if not getImage(imageLink, lcscPart):
                        imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_front_11.jpg'

                        if not getImage(imageLink, lcscPart):
                            imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20280914_' + splitDatasheet[0] + '_front.jpg'
                            
                            if not getImage(imageLink, lcscPart):
                                imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_1.jpg'
                                
                                if not getImage(imageLink, lcscPart):                                       
                                    imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + splitDatasheet[0] + '_package.jpg'
                                    
                                    if not getImage(imageLink, lcscPart):
                                        with open(failedPartsFile, 'a') as failedParts:
                                            failedParts.write(imageFilename + '\n')
                                            
                                        imageFilename = defaultImage
        except:
            print('Error: problem trying to parse datasheet entry: {0}'.format(datasheet))
            imageFilename = defaultImage

    return imageFilename

class ImgLabel(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, img):
        super(ImgLabel, self).__init__()
        self.pixmap = QPixmap(img)

    def paintEvent(self, event):
        size = self.size()
        painter = QPainter(self)
        point = QPoint(0,0)
        scaledPix = self.pixmap.scaled(size, Qt.KeepAspectRatio, transformMode = Qt.SmoothTransformation)
        # start painting the label from left upper corner
        point.setX(int((size.width() - scaledPix.width())/2))
        point.setY(int((size.height() - scaledPix.height())/2))
        painter.drawPixmap(point, scaledPix)    

    def mousePressEvent(self, ev):
        self.clicked.emit()
    
class LinkLabel(QLabel):    
    def __init__(self, img):
        super().__init__()
        self.setOpenExternalLinks(True)
        
class JlcSearch(QDialog):
    def __init__(self, parent=None):
        super(JlcSearch, self).__init__(parent)
        
        self.originalPalette = QApplication.palette()
        self.setMinimumSize(930, 300)
        
        expandPolicy = QSizePolicy()
        expandPolicy.setHorizontalPolicy(QSizePolicy.Expanding)

        self.converting = False
        
        self.tabWidget = QTabWidget()

        tabsLayout = QHBoxLayout()
        tabsLayout.addWidget(self.tabWidget)
        
        convertTab = QWidget()
        self.downloadLink = LinkLabel(self)
        self.downloadLink.setText('<a href={0}>{1}</a>'.format('https://jlcpcb.com/componentSearch/uploadComponentInfo', 'Download CSV from: https://jlcpcb.com/componentSearch/uploadComponentInfo'))

        self.csvFile = QComboBox()
        self.csvFile.setSizePolicy(expandPolicy)
        
        csvFiles = glob.glob('*.csv')
            
        # If there are some files in the directory, show them
        if len(csvFiles):
            for file in csvFiles:
                self.csvFile.addItem(file)
        else:
            self.getCsvFile()
        self.csvFileLabel = QLabel("CSV File:")
        self.csvFileLabel.setBuddy(self.csvFile)
        self.findFiles = QPushButton("Find Files")
        self.findFiles.clicked.connect(self.getCsvFile)
        self.cacheAllImages = QCheckBox("Force all images to be cached (takes hours and gigabytes of disk space!)")
        self.clearFailedImages = QCheckBox("Clear list of failed images")
        self.dbFileName = QLineEdit(defaultDbFile)
        self.dbFileNameLabel = QLabel("Database Filename:")
        self.dbFileNameLabel.setBuddy(self.dbFileName)
        
        csvFileLayout = QHBoxLayout()
        csvFileLayout.addWidget(self.csvFileLabel)
        csvFileLayout.addWidget(self.csvFile)
        csvFileLayout.addWidget(self.findFiles)
        
        dbFileLayout = QHBoxLayout()
        dbFileLayout.addWidget(self.dbFileNameLabel)
        dbFileLayout.addWidget(self.dbFileName)
        
        self.convertNow = QPushButton("Convert To Database")
        self.convertNow.clicked.connect(self.convertProcedure)
        
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 10000)
        self.progressBar.setValue(0)
        
        convertLayout = QGridLayout()
        convertLayout.addWidget(self.downloadLink, 0, 0, 2, 2)
        convertLayout.addLayout(csvFileLayout, 1, 0, 2, 2)
        convertLayout.addWidget(self.cacheAllImages, 2, 0, 2, 1)
        convertLayout.addWidget(self.clearFailedImages, 2, 1, 2, 1)
        convertLayout.addLayout(dbFileLayout, 3, 0, 2, 2)
        convertLayout.addWidget(self.convertNow, 4, 0, 2, 1)
        convertLayout.addWidget(self.progressBar, 5, 0, 2, 2)

        convertTab.setLayout(convertLayout)

        searchTab = QWidget()
        self.keywords = QLineEdit()
        self.keywordLabel = QLabel("Keywords:")
        self.keywordLabel.setBuddy(self.keywords)
        self.packages = QLineEdit()
        self.packageLabel = QLabel("Packages:")
        self.packageLabel.setBuddy(self.packages)
        self.sortType = QPushButton("Sort Stock Down")
        self.sortValue = SortEnum.SORT_STOCK_DOWN
        self.sortType.clicked.connect(self.sortType_clicked)
        self.update = QPushButton("Update")
        self.update.clicked.connect(self.update_clicked)
        self.useExtendedCheckBox = QCheckBox("Extended Parts")
        #self.useExtendedCheckBox.setChecked(True)
        self.loadImages = QCheckBox("Load Images")
        self.loadImages.setChecked(True)
        self.tableWidget = QTableWidget(0, TableColumnEnum.TABLE_COL_COUNT)
        self.tableWidget.setHorizontalHeaderLabels(['LCSC Part','Type','Description','Package','Manf','Price','Stock','Image'])
        verticalHeader = self.tableWidget.verticalHeader()
        verticalHeader.setMinimumSectionSize(100)
        self.tableWidget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_PART, 60)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_EXT, 60)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_DESC, 210)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_PKG, 90)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_MANF, 120)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_PRICE, 130)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_STOCK, 60)
        self.tableWidget.setColumnWidth(TableColumnEnum.TABLE_COL_IMAGE, 100)

        
        '''
            Search tab layout
        '''
        topLayout = QHBoxLayout()
        topLayout.addWidget(self.keywordLabel)
        topLayout.addWidget(self.keywords)
        topLayout.addWidget(self.packageLabel)
        topLayout.addWidget(self.packages)
        topLayout.addWidget(self.useExtendedCheckBox)
        topLayout.addWidget(self.loadImages)
        topLayout.addWidget(self.sortType)
        topLayout.addWidget(self.update)
        
        searchLayout = QGridLayout()
        searchLayout.addLayout(topLayout, 0, 0, 1, 2)
        searchLayout.addWidget(self.tableWidget)
        searchTab.setLayout(searchLayout)

        '''
            Tabs top level
        '''
        self.tabWidget.addTab(convertTab, "Convert")
        self.tabWidget.addTab(searchTab, "Search")
        self.setLayout(tabsLayout)
        
        if os.path.isfile(self.dbFileName.text()):
            self.tabWidget.setCurrentIndex(1)

        self.setWindowTitle("JLCPCP Parts Search")
        QApplication.setStyle(QStyleFactory.create(('Fusion')))
    
    def getCsvFile(self):
        fname = QFileDialog.getOpenFileName(self, caption='CSV FIle', filter='*.csv')
        self.csvFile.clear()
        self.csvFile.addItem(fname[0])

            
    def convertProcedure(self):
        # Abort Mechanism not working, needs a thread
        if self.converting == True:
            self.converting = False
            self.convertNow.setText("Convert To Database")
        else:
            self.converting = True
            self.convertNow.setText("Abort")
            
            try:
                os.remove(self.dbFileName.text())
            except:
                pass
            
            con = sqlite3.connect(self.dbFileName.text())
            cur = con.cursor()
            
            currentImageList = os.listdir(imageCacheDir)
            
            try:
                if self.clearFailedImages.isChecked():
                    os.remove(failedPartsFile)
                else:
                    with open(failedPartsFile, 'r') as failedParts:
                        failedPartsList = failedParts.read().splitlines()
            except:
                failedPartsList = []
            
            # Create table
            cur.execute('''CREATE TABLE jlc
                           (LCSCPart, FirstCategory, SecondCategory, MFRPart, Package, SolderJoint, Manufacturer, LibraryType, Description, Datasheet, Price, Stock, worstPrice, image)''')
            
            # This is naff, csv.reader has no method for getting the number of records so you have to parse twice!!
            with open(self.csvFile.currentText()) as csvFile:
                row_count = sum(1 for line in csvFile)
                
            with open(self.csvFile.currentText(), newline='') as csvFile:
                reader = csv.reader(csvFile,delimiter=',')            
    
                rowIndex = 0;
                self.progressBar.setValue(0)                
                self.converting = True
    
                for row in reader:
                    # Abort mechanism
                    if not self.converting == False:
                        imageFileName = ''
                        
                        # The first line in JLC files is a header
                        if len(row) == 13:
                            if self.cacheAllImages.isChecked():
                                imageFilename = row[DbRowEnum.DB_ROW_LCSC_PART] + '.jpg'
                                if imageFilename not in currentImageList and imageFilename not in failedPartsList:
                                    imageFileName = getImageFilename(row[DbRowEnum.DB_ROW_DATASHEET], row[DbRowEnum.DB_ROW_LCSC_PART])
                                else:
                                    imageFilename = defaultImage
                                
                            prices = row[10].split(',')
                            worstPrice = 0.0
                            thisPrice = 0.0
                            for price in prices:
                                # Boil down lists of prices to be just the highest price (usually lowest number)
                                priceFor = price.split(':')
                                
                                if len(priceFor) > 1:
                                    pricePart = priceFor[1]
                                else:
                                    # Not a range of prices
                                    pricePart = price
                
                                try:
                                    thisPrice = float(priceFor[1])
                                except:
                                    # Sometimes the price is nonsense or omitted
                                    thisPrice = 99999999
                                    
                                if thisPrice > worstPrice:
                                    worstPrice = thisPrice
                            
                            row[12] = worstPrice
                            
                            row.append(imageFileName)
                            cur.execute("INSERT INTO jlc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
                            
                            rowIndex += 1
    
                            self.progressBar.setValue(1 + int((rowIndex*10000)/row_count))
                            QApplication.processEvents()
                            
            self.converting = False
            self.convertNow.setText("Convert To Database")
                        
            # Save changes
            con.commit()
            con.close()
        
    def handleDb(self):        
        if not os.path.isfile(self.dbFileName.text()):
            error_dialog = QErrorMessage()
            error_dialog.showMessage('Can\'t find database file: {0}'.format(self.dbFileName.text()))
            error_dialog.exec_()
        else:
            self.con = sqlite3.connect(self.dbFileName.text())
    
            cur = self.con.cursor()
            
            currentImageList = os.listdir(imageCacheDir)
            
            try:
                with open(failedPartsFile, 'r') as failedParts:
                    failedPartsList = failedParts.read().splitlines()
            except:
                failedPartsList = []
    
            sqlCommand = "SELECT * FROM jlc WHERE "
            if not self.useExtendedCheckBox.isChecked():
                sqlCommand += "LibraryType='Basic' AND "
            
            firstCondition = True
            keyWordList = self.keywords.text().split()
    
            if len(keyWordList) > 0:
                sqlCommand += "("
                for keyWord in keyWordList:
                    if not firstCondition:
                        sqlCommand += "AND "
                    firstCondition = False
                    sqlCommand += "(LOWER(FirstCategory) LIKE LOWER('%{0}%') OR LOWER(SecondCategory) LIKE LOWER('%{0}%') OR LOWER(Description) LIKE LOWER('%{0}%') OR LOWER(MFRPart) LIKE LOWER('%{0}%') OR LOWER(LCSCPart) = LOWER('{0}')) ".format(keyWord)
                sqlCommand += ") "
                
                packagesList = self.packages.text().split()
                firstCondition = True
                if len(packagesList) > 0:
                    sqlCommand += "AND ("
                    for package in packagesList:
                        if not firstCondition:
                            sqlCommand += "OR "
                        firstCondition = False
        
                        sqlCommand += "LOWER(Package) LIKE LOWER('%{0}%') ".format(package)
                    sqlCommand += ") "
    
                if self.sortValue == SortEnum.SORT_STOCK_DOWN:
                    sqlCommand += "AND Stock > 0 ORDER BY CAST(Stock AS INTEGER) DESC"
                elif self.sortValue == SortEnum.SORT_PRICE_UP:
                    sqlCommand += "ORDER BY WorstPrice ASC"
                elif self.sortValue == SortEnum.SORT_IN_STOCK_PRICE_UP:
                    sqlCommand += "AND Stock > 0 ORDER BY WorstPrice ASC"
        
                #print(sqlCommand)
                            
                cur.execute(sqlCommand)
    
                rows = cur.fetchall()
                                
                self.tableWidget.setRowCount(0)
                
                linkTemplate = '<a href={0}>{1}</a>'      
    
                for row in rows:
                    rowPosition = self.tableWidget.rowCount()
                    self.tableWidget.insertRow(rowPosition)
                    
                    # Add up to 4 price ranges
                    prices = row[DbRowEnum.DB_ROW_PRICE].split(',')
                    priceField = prices[0]
                    if len(prices) > 1:
                        priceField +=  '\n' + prices[1]
                    if len(prices) > 2:
                        priceField +=  '\n' + prices[2]
                    if len(prices) > 3:
                        priceField +=  '\n' + prices[3]
                    
                    if row[DbRowEnum.DB_ROW_DATASHEET].strip() == '':   
                        self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_PART,  QTableWidgetItem(row[DbRowEnum.DB_ROW_LCSC_PART]))
                    else:
                        linkLabel = LinkLabel(self)
                        linkLabel.setText('<a href={0}>{1}</a>'.format(row[DbRowEnum.DB_ROW_DATASHEET], row[DbRowEnum.DB_ROW_LCSC_PART]))
                        self.tableWidget.setCellWidget(rowPosition, TableColumnEnum.TABLE_COL_PART, linkLabel)

                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_EXT,   QTableWidgetItem(row[DbRowEnum.DB_ROW_LIB_TYPE]))
                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_DESC,  QTableWidgetItem(row[DbRowEnum.DB_ROW_SEC_CAT] + ' ' + row[DbRowEnum.DB_ROW_DESCR]))
                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_PKG,   QTableWidgetItem(str(row[DbRowEnum.DB_ROW_PACKAGE]).replace('_','\n')))
                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_MANF,  QTableWidgetItem(row[DbRowEnum.DB_ROW_MANF] + '\n' + row[DbRowEnum.DB_ROW_MFR_PART]))
                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_PRICE, QTableWidgetItem(priceField))
                    self.tableWidget.setItem(rowPosition, TableColumnEnum.TABLE_COL_STOCK, QTableWidgetItem(row[DbRowEnum.DB_ROW_STOCK]))
                    
                    imageFilename = row[DbRowEnum.DB_ROW_LCSC_PART] + '.jpg'
                    imageNotInFailedList = False
                    if imageFilename not in failedPartsList:
                        imageNotInFailedList = True
                        if imageFilename not in currentImageList:
                            if self.loadImages.isChecked():
                                imageFileName = getImageFilename(row[DbRowEnum.DB_ROW_DATASHEET], row[DbRowEnum.DB_ROW_LCSC_PART])
                                if imageFilename == defaultImage:
                                    imageNotInFailedList = False
                            else:
                                imageFilename = defaultImage
                    else:
                        imageFilename = defaultImage
                                        
                    imgLabel = ImgLabel(imageCacheDir + imageFilename)
                    imgLabel.setScaledContents(True)
                    
                    # If it might have been possible to download the image, clicking will do that
                    if (imageFilename == defaultImage) and imageNotInFailedList:
                        imgLabel.clicked.connect(partial(self.imageClicked, row[DbRowEnum.DB_ROW_LCSC_PART], row[DbRowEnum.DB_ROW_DATASHEET]))
    
                    tooltip = '<img src="'+ imageCacheDir + imageFilename + '" width="300" height="300">'
                    imgLabel.setToolTip(tooltip)
    
                    self.tableWidget.setCellWidget(rowPosition, TableColumnEnum.TABLE_COL_IMAGE, imgLabel)

    def imageClicked(self, part, datasheet):
        imageFilename = getImageFilename(datasheet, part)
        if imageFilename != defaultImage:
            self.handleDb()

    def sortType_clicked(self):
        if self.sortValue == SortEnum.SORT_STOCK_DOWN:
            self.sortType.setText("Sort Price Up")
            self.sortValue = SortEnum.SORT_PRICE_UP            
        elif self.sortValue == SortEnum.SORT_PRICE_UP:
            self.sortType.setText("Sort In Stock Price Up")
            self.sortValue = SortEnum.SORT_IN_STOCK_PRICE_UP
        else:
            self.sortType.setText("Sort Stock Down")
            self.sortValue = SortEnum.SORT_STOCK_DOWN
        

    def update_clicked(self):
        self.update.setText("Searching")
        QApplication.processEvents() 
        self.handleDb()
        self.update.setText("Update")

if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    dialogApp = JlcSearch()
    dialogApp.show()
    sys.exit(app.exec_()) 

