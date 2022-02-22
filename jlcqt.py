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
import re

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
    DB_ROW_MIN_QUANTITY = 13
    DB_ROW_IMAGE = 14

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

class BomColumnEnum(IntEnum):
    BOM_COL_COMMENT = 0
    BOM_COL_DES = 1
    BOM_COL_FOOT = 2
    BOM_COL_PART = 3
    BOM_COL_BASIC = 4
    BOM_COL_PRICE = 5
    BOM_COL_STOCK = 6
    BOM_COL_IMAGE = 7
    BOM_COL_COUNT = 8

class JlcCsvColumnEnum(IntEnum):
    JLC_CSV_COMMENT = 0
    JLC_CSV_DES = 1
    JLC_CSV_FOOT = 2
    JLC_CSV_PART = 3
    JLC_CSV_COUNT = 4

imageCacheDir = 'imageCache/'
failedPartsFile = imageCacheDir +'failedParts.txt'
defaultImage = 'no_image.png'
defaultDbFile = 'jlc.db'
defaultBomOutFile = 'jlcBom.csv'
                 
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
        
def getimageFilename(row, failedPartsList):
    lcscPart = row[DbRowEnum.DB_ROW_LCSC_PART]
    imageFilename = lcscPart + '.jpg'
    
    if row[DbRowEnum.DB_ROW_DATASHEET].strip() == '':
        # If there's no datasheet, best guess to image name is manufacture-partNumber_lcscPartNumber
        partialImageName = row[DbRowEnum.DB_ROW_MANF] + '-' + row[DbRowEnum.DB_ROW_MFR_PART] + '_' + row[DbRowEnum.DB_ROW_LCSC_PART]
    else:
        try:
            # Extract the part of the datasheet name that is useful
            splitDatasheet = row[DbRowEnum.DB_ROW_DATASHEET].split('_', 1)
            splitDatasheet = splitDatasheet[1].rsplit('.', 1)
            partialImageName = splitDatasheet[0]
        except:
            return defaultImage
    
    '''
     There are a number of variations of the url for the image - some of which look like typos
     All are based on the datasheet name (for want of a better algorithm)
    '''
    imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_front.jpg'
    
    if not getImage(imageLink, lcscPart):
        imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_front_10.jpg'

        if not getImage(imageLink, lcscPart):
            imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_front_10.JPG'

            if not getImage(imageLink, lcscPart):
                imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_front_11.jpg'

                if not getImage(imageLink, lcscPart):
                    imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20280914_' + partialImageName + '_front.jpg'
                    
                    if not getImage(imageLink, lcscPart):
                        imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_1.jpg'
                        
                        if not getImage(imageLink, lcscPart):                                       
                            imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20180914_' + partialImageName + '_package.jpg'
                            
                            if not getImage(imageLink, lcscPart):                                       
                                imageLink = 'https://assets.lcsc.com/images/lcsc/900x900/20200421_' + partialImageName + '_front.jpg'
                            
                                if not getImage(imageLink, lcscPart):
                                    with open(failedPartsFile, 'a') as failedParts:
                                        failedParts.write(lcscPart + '.jpg\n')
                                        failedPartsList.append(lcscPart + '.jpg')
                                    
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
                    
class PartAndDatasheetWidget(QWidget):
    def __init__(self, partNum, datasheetLink):
        #super(PartAndDatasheetWidget,self).__init__(None)
        super().__init__()
        layout = QGridLayout()
        self.lcscPartNumber = partNum
        partLinkLabel = QLabel(self)
        partLinkLabel.linkActivated.connect(self.openLink)
        partLinkLabel.setText("<a href=https://lcsc.com/search?q%3d{0}>{1}</a>".format(partNum, partNum))
        layout.addWidget(partLinkLabel)
        if datasheetLink != '':
            datasheetLinkLabel = QLabel(self)
            datasheetLinkLabel.linkActivated.connect(self.openLink)
            datasheetLinkLabel.setText(datasheetLink)
            layout.addWidget(datasheetLinkLabel)
        self.setLayout(layout)

    def openLink(self, linkStr):
        QDesktopServices.openUrl(QUrl(linkStr.replace('%3d','=')))
       
    def getLcscPartNumber(self):
        #return re.search('>(.*?)<', self.partLinkLabel.text()).group(1)
        return self.lcscPartNumber

                        
                                        
class PartTable(QTableWidget):
        def __init__(self, currentImageList, failedImageList):
            super().__init__(0, TableColumnEnum.TABLE_COL_COUNT)
            self.setHorizontalHeaderLabels(['LCSC Part','Type','Description','Package','Manf','Price','Stock','Image'])
            verticalHeader = self.verticalHeader()
            verticalHeader.setMinimumSectionSize(100)
            self.setEditTriggers(QTableWidget.NoEditTriggers)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_PART, 80)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_EXT, 60)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_DESC, 210)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_PKG, 90)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_MANF, 120)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_PRICE, 130)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_STOCK, 60)
            self.setColumnWidth(TableColumnEnum.TABLE_COL_IMAGE, 100)
            
            self.currentImageList = currentImageList
            self.failedPartsList = failedImageList
        
            
        def getSelectedLcscPartNumber(self, rowIndex):
            return self.cellWidget(rowIndex, TableColumnEnum.TABLE_COL_PART).getLcscPartNumber()
        
        def imageClicked(self, row, imgLabel):
            imageFilename = getimageFilename(row, self.failedPartsList)
            if imageFilename != defaultImage:
                imgLabel.pixmap = QPixmap(imageCacheDir + imageFilename)
                imgLabel.repaint()
        
        def openLink(self, linkStr):
                QDesktopServices.openUrl(QUrl(linkStr.replace('%3d','=')))
        
        def searchPopulate(self, rows, downloadImages):                                
            self.setRowCount(0)                

            for row in rows:
                rowPosition = self.rowCount()
                self.insertRow(rowPosition)
                
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
                    datasheetLinkText = ''                  
                else:
                    datasheetLinkText = "<a href={0}>Datasheet</a>".format(row[DbRowEnum.DB_ROW_DATASHEET])
                partAndDatasheetWidget = PartAndDatasheetWidget(row[DbRowEnum.DB_ROW_LCSC_PART], datasheetLinkText)
                self.setCellWidget(rowPosition, TableColumnEnum.TABLE_COL_PART, partAndDatasheetWidget)

                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_EXT,   QTableWidgetItem(row[DbRowEnum.DB_ROW_LIB_TYPE]))
                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_DESC,  QTableWidgetItem(row[DbRowEnum.DB_ROW_SEC_CAT] + ' ' + row[DbRowEnum.DB_ROW_DESCR]))
                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_PKG,   QTableWidgetItem(str(row[DbRowEnum.DB_ROW_PACKAGE]).replace('_','\n')))
                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_MANF,  QTableWidgetItem(row[DbRowEnum.DB_ROW_MANF] + '\n' + row[DbRowEnum.DB_ROW_MFR_PART]))
                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_PRICE, QTableWidgetItem(priceField))
                self.setItem(rowPosition, TableColumnEnum.TABLE_COL_STOCK, QTableWidgetItem(row[DbRowEnum.DB_ROW_STOCK]))
                
                imageFilename = row[DbRowEnum.DB_ROW_LCSC_PART] + '.jpg'

                imageNotInFailedList = False
                if imageFilename not in self.failedPartsList:
                    imageNotInFailedList = True
                    if imageFilename not in self.currentImageList:
                        if downloadImages:
                            imageFilename = getimageFilename(row, self.failedPartsList)
                            if imageFilename == defaultImage:
                                imageNotInFailedList = False
                        else:
                            imageFilename = defaultImage
                else:
                    imageFilename = defaultImage
                                    
                imgLabel = ImgLabel(imageCacheDir + imageFilename)
                imgLabel.setScaledContents(True)
                
                # If it might have been possible to download the image, clicking will do that
                if imageFilename == defaultImage:
                    if imageNotInFailedList:
                        imgLabel.clicked.connect(partial(self.imageClicked, row, imgLabel))
                        imgLabel.setToolTip('Click to try to download image')
                else:
                    imgLabel.clicked.connect(partial(self.imageClicked, row, imgLabel))
                    tooltip = '<img src="'+ imageCacheDir + imageFilename + '" width="300" height="300">'
                    imgLabel.setToolTip(tooltip)

                self.setCellWidget(rowPosition, TableColumnEnum.TABLE_COL_IMAGE, imgLabel)


class JlcSearch(QDialog):
    def __init__(self, parent=None):
        super(JlcSearch, self).__init__(parent)
        
        self.originalPalette = QApplication.palette()
        self.setMinimumSize(930, 300)
        
        expandPolicy = QSizePolicy()
        expandPolicy.setHorizontalPolicy(QSizePolicy.Expanding)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.converting = False
        
        # Get the available images and the never-to-be-available images into 2 lists
        self.currentImageList = os.listdir(imageCacheDir)
        
        try:
            with open(failedPartsFile, 'r') as failedParts:
                self.failedPartsList = failedParts.read().splitlines()
        except:
            self.failedPartsList = []
                
        
        self.tabWidget = QTabWidget()

        tabsLayout = QHBoxLayout()
        tabsLayout.addWidget(self.tabWidget)
        
        convertTab = QWidget()
        self.downloadLink = LinkLabel(self)
        self.downloadLink.setText('<a href={0}>{1}</a>'.format('https://jlcpcb.com/componentSearch/uploadComponentInfo', 'Download CSV from: https://jlcpcb.com/componentSearch/uploadComponentInfo'))

        self.csvFile = QComboBox()
        self.csvFile.setSizePolicy(expandPolicy)
        
        csvFiles = glob.glob('*.csv')
        
        self.selectingNewPart = False
        self.populatingBomTable = False
            
        # If there are some files in the directory, show them
        if len(csvFiles):
            for file in csvFiles:
                self.csvFile.addItem(file)
        else:
            self.getCsvFile(self.csvFile)
        self.csvFileLabel = QLabel("CSV File:")
        self.csvFileLabel.setBuddy(self.csvFile)
        self.findFiles = QPushButton("Find Files")
        self.findFiles.clicked.connect(partial(self.getCsvFile, self.csvFile))
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
        self.convertStatus = QLabel()

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 10000)
        self.progressBar.setValue(0)
        
        ''' Convert tab widgets
        '''
        convertLayout = QGridLayout()
        convertLayout.addWidget(self.downloadLink, 0, 0, 2, 2)
        convertLayout.addLayout(csvFileLayout, 1, 0, 2, 2)
        convertLayout.addWidget(self.cacheAllImages, 2, 0, 2, 1)
        convertLayout.addWidget(self.clearFailedImages, 2, 1, 2, 1)
        convertLayout.addLayout(dbFileLayout, 3, 0, 2, 2)
        convertLayout.addWidget(self.convertNow, 4, 0, 2, 1)
        convertLayout.addWidget(self.convertStatus, 4, 1, 2, 1)
        convertLayout.addWidget(self.progressBar, 5, 0, 2, 2)

        convertTab.setLayout(convertLayout)

        ''' Search Tab widgets
        '''
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
        
        self.partTable = PartTable(self.currentImageList, self.failedPartsList)
        self.partTable.itemSelectionChanged.connect(self.partSelected)

        
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
        searchLayout.addWidget(self.partTable)
        searchTab.setLayout(searchLayout)

        ''' BOM Tab widgets
        '''
        bomTab = QWidget()
        self.bomFile = QComboBox()
        self.bomFile.setSizePolicy(expandPolicy)
        csvFiles = glob.glob('*.csv')
            
        # If there are some files in the directory, show them
        if len(csvFiles):
            for file in csvFiles:
                self.bomFile.addItem(file)
        else:
            self.getCsvFile(self.bomFile)
        self.bomFile.currentIndexChanged.connect(self.bomPopulateTable)        

        self.findBoms = QPushButton("Find")
        self.findBoms.clicked.connect(partial(self.getCsvFile, self.bomFile))
        self.bomSrcLabel = QLabel("BOM Source:")
        self.bomSrcLabel.setBuddy(self.bomFile)
            
        self.bomSrcType = QComboBox()
        self.bomSrcType.addItem('JLC')
        self.bomSrcTypeLabel = QLabel("BOM Nature:")
        self.bomSrcTypeLabel.setBuddy(self.bomSrcType)
        self.bomSelectType = QPushButton("Highest Stock")
        self.bomSelectValue = SortEnum.SORT_STOCK_DOWN
        #self.bomSelectType.clicked.connect(self.bomSelectType_clicked)
        self.useExtendedinBomCheckBox = QCheckBox("Extended Parts")
        #self.useExtendedinBomCheckBox.setChecked(True)

        self.bomSearchForParts = QPushButton("Search For Parts")
        self.bomWriteButton = QPushButton("Write BOM")
                      
        self.bomTable = QTableWidget(0, BomColumnEnum.BOM_COL_COUNT)
        self.bomTable.setHorizontalHeaderLabels(['Comment','Designator','Footprint','LCSC Part', 'Basic','Price', 'Stock', 'Image'])
        verticalHeader = self.bomTable.verticalHeader()
        verticalHeader.setMinimumSectionSize(50)
        self.bomTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_COMMENT, 210)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_DES, 60)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_FOOT, 210)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_BASIC, 50)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_PART, 90)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_PRICE, 130)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_STOCK, 60)
        self.bomTable.setColumnWidth(BomColumnEnum.BOM_COL_IMAGE, 50)
        self.bomTable.itemSelectionChanged.connect(self.bomPartSelect)
        self.bomSearchForParts.clicked.connect(self.bomSearch)
        self.bomWriteButton.clicked.connect(self.bomWrite)

        '''
            BOM tab layout
        '''
        bomCtrlLayout = QHBoxLayout()
        bomCtrlLayout.addWidget(self.bomSrcLabel)
        bomCtrlLayout.addWidget(self.bomFile)
        bomCtrlLayout.addWidget(self.findBoms)
        
        bomCtrlLayout.addWidget(self.bomSrcTypeLabel)
        bomCtrlLayout.addWidget(self.bomSrcType)
        bomCtrlLayout.addWidget(self.useExtendedinBomCheckBox)
        bomCtrlLayout.addWidget(self.bomSelectType)
        bomCtrlLayout.addWidget(self.bomSearchForParts)
        bomCtrlLayout.addWidget(self.bomWriteButton)
        
        bomLayout = QGridLayout()
        bomLayout.addLayout(bomCtrlLayout, 0, 0, 1, 2)
        bomLayout.addWidget(self.bomTable)
        bomTab.setLayout(bomLayout)

                
        '''
            Tabs top level
        '''
        self.tabWidget.addTab(convertTab, "Convert")
        self.tabWidget.addTab(searchTab, "Search")
        self.tabWidget.addTab(bomTab, "BOM")
        self.setLayout(tabsLayout)
        
        if os.path.isfile(self.dbFileName.text()):
            self.tabWidget.setCurrentIndex(1)

        self.setWindowTitle("JLCPCP Parts Search")
        QApplication.setStyle(QStyleFactory.create(('Fusion')))
    
    def getCsvFile(self, qlist):
        fname = QFileDialog.getOpenFileName(self, caption='CSV FIle', filter='*.csv')
        qlist.clear()
        qlist.addItem(fname[0])

    def fixUpOddChars(self, rawString):
        # Use a dictionary of string conversions
        replacements = {u'\xa6\xcc': 'u',   # micro
                        u'\xa6\xb8': 'R',   # Ohms
                        u'\xa1\xc0': '+/-', # Plus or minus
                        u'\xa1\xe6': 'C',   # Celcius
                        u'\xa3\xa5': '%'    # Percent
                        }

        replacements = {key: val for key, val in replacements.items()}
        pattern = re.compile("|".join(replacements))
        newString = pattern.sub(lambda match: replacements[match.group(0)], rawString)  
        return newString
    
    def imageClicked(self, row, imgLabel):
        imageFilename = getimageFilename(row, self.failedPartsList)
        if imageFilename != defaultImage:
            imgLabel.pixmap = QPixmap(imageCacheDir + imageFilename)
            imgLabel.repaint()
    
    def bomWrite(self):
        with open(defaultBomOutFile, 'w') as bomFile:
            bomFile.write('Comment,Designator,Footprint,LCSC Part #\n')
            
            self.bomWriteButton.setText("Writing...")
            QApplication.processEvents()

            for rowIndex in range(self.bomTable.rowCount()):
                commentData = self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_COMMENT).text()
                designator = self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_DES).text()
                footprintData = self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_FOOT).text()
                lcscPart = self.bomTable.cellWidget(rowIndex, BomColumnEnum.BOM_COL_PART).getLcscPartNumber()

                bomFile.write(commentData + ',' + designator + ',' + footprintData + ',' + lcscPart + '\n')
            
            print("BOM Written")
            self.bomWriteButton.setText("Write BOM")
        
    def bomPopulateRow(self, rowPosition, bomData):
        if not os.path.isfile(self.dbFileName.text()):
            error_dialog = QErrorMessage()
            error_dialog.showMessage('Can\'t find database file: {0}'.format(self.dbFileName.text()))
            error_dialog.exec_()
        else:
            self.con = sqlite3.connect(self.dbFileName.text())

            cur = self.con.cursor()

            self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_COMMENT,   QTableWidgetItem(bomData[BomColumnEnum.BOM_COL_COMMENT]))
            self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_DES,   QTableWidgetItem(bomData[BomColumnEnum.BOM_COL_DES]))
            self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_FOOT,   QTableWidgetItem(bomData[BomColumnEnum.BOM_COL_FOOT]))
            self.bomTable.setCellWidget(rowPosition, BomColumnEnum.BOM_COL_PART, PartAndDatasheetWidget(bomData[BomColumnEnum.BOM_COL_PART], '')) 
                #self.setItem(rowPosition, BomColumnEnum.BOM_COL_PART,   QTableWidgetItem(row[BomColumnEnum.BOM_COL_PART]))
                
            if bomData[BomColumnEnum.BOM_COL_PART] != '':                            
                cur.execute("SELECT * FROM jlc WHERE LCSCPart = '{0}'".format(bomData[BomColumnEnum.BOM_COL_PART]))
                dbRows = cur.fetchall()
                
                # Hopefully there's only one row
                if len(dbRows) >= 1:
                    dbData = dbRows[0]
                    if dbData[DbRowEnum.DB_ROW_LIB_TYPE] == 'Basic':
                        typeMarker = 'Y'
                    else:
                        typeMarker = 'N'

                    self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_BASIC,   QTableWidgetItem(typeMarker))
                    pricePer = round(dbData[DbRowEnum.DB_ROW_WORST_PRICE]/dbData[DbRowEnum.DB_ROW_MIN_QUANTITY],4)
                    
                    self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_PRICE,   QTableWidgetItem(str(pricePer)))
                    self.bomTable.setItem(rowPosition, BomColumnEnum.BOM_COL_STOCK,   QTableWidgetItem(str(dbData[DbRowEnum.DB_ROW_STOCK])))

            
                imageFilename = bomData[BomColumnEnum.BOM_COL_PART] + '.jpg'

                if imageFilename not in self.currentImageList:
                    imageFilename = defaultImage
                                    
                imgLabel = ImgLabel(imageCacheDir + imageFilename)
                imgLabel.setScaledContents(True)
                
                if imageFilename != defaultImage:
                    tooltip = '<img src="'+ imageCacheDir + imageFilename + '" width="300" height="300">'
                    imgLabel.setToolTip(tooltip)

                self.bomTable.setCellWidget(rowPosition, BomColumnEnum.BOM_COL_IMAGE, imgLabel)
        
    def bomPopulateTable(self):
        with open(self.bomFile.currentText()) as csvFile:
            self.numBomRows = sum(1 for line in csvFile)
        
        jlcBom = []
        with open(self.bomFile.currentText(), newline='') as csvFile:
            reader = csv.reader(csvFile,delimiter=',')
            self.bomTable.setCurrentCell(0,0)
            self.populatingBomTable = True
            for row in reader:
                if len(row) and row[JlcCsvColumnEnum.JLC_CSV_COMMENT] != 'Comment':
                    jlcBom.append([row[JlcCsvColumnEnum.JLC_CSV_COMMENT],
                                   row[JlcCsvColumnEnum.JLC_CSV_DES],
                                   row[JlcCsvColumnEnum.JLC_CSV_FOOT],
                                   row[JlcCsvColumnEnum.JLC_CSV_PART]])
                                        

            self.bomTable.setRowCount(0)
            for row in jlcBom:
                rowPosition = self.bomTable.rowCount()
                self.bomTable.insertRow(rowPosition)
                self.bomPopulateRow(rowPosition, row)
        self.populatingBomTable = False
    
    def openLink(self, linkStr):
        QDesktopServices.openUrl(QUrl(linkStr.replace('%3d','=')))
        
    def bomPartSelect(self):
        if not self.populatingBomTable:
            currentRow = self.bomTable.currentRow()
            self.keywords.setText(self.bomTable.item(currentRow, BomColumnEnum.BOM_COL_COMMENT).text())
            self.packages.setText(self.bomTable.item(currentRow, BomColumnEnum.BOM_COL_FOOT).text().replace('_', ' '))
            self.useExtendedCheckBox.setChecked(self.useExtendedinBomCheckBox.isChecked())
            self.selectingNewPart = True
            self.tabWidget.setCurrentIndex(1)
            self.update_clicked()

    def partSelected(self):
        if self.selectingNewPart:
            currentRow = self.partTable.currentRow()
            newLcscPart = self.partTable.getSelectedLcscPartNumber(currentRow)
            newRow = [self.bomTable.itemAt(currentRow, BomColumnEnum.BOM_COL_COMMENT).text(),
                      self.bomTable.itemAt(currentRow, BomColumnEnum.BOM_COL_DES).text(),
                      self.bomTable.itemAt(currentRow, BomColumnEnum.BOM_COL_FOOT).text(),
                      newLcscPart]
            self.selectingNewPart = False
            self.tabWidget.setCurrentIndex(2)

        
    def bomSearch(self):
        if not os.path.isfile(self.dbFileName.text()):
            error_dialog = QErrorMessage()
            error_dialog.showMessage('Can\'t find database file: {0}'.format(self.dbFileName.text()))
            error_dialog.exec_()
        else:
            self.con = sqlite3.connect(self.dbFileName.text())

            self.bomSearchForParts.setText("Searching...")
            QApplication.processEvents()

            cur = self.con.cursor()
                        
            # Populate in reversed so you can definitely see last item updated
            for rowIndex in reversed(range(self.bomTable.rowCount())):
                commentData = self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_COMMENT).text().split(' ')
                footprintData = self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_FOOT).text().split('_')
                
                sqlCommand = "SELECT * FROM jlc WHERE "
                
                if not self.useExtendedinBomCheckBox.isChecked():
                    sqlCommand += "LibraryType='Basic' AND "
                    
                firstCondition = True

                if len(commentData) > 0:
                    sqlCommand += "("
                    for keyWord in commentData:
                        if not firstCondition:
                            sqlCommand += "AND "
                        firstCondition = False
                    
                        keyWord = keyWord.lower()
                        sqlCommand += "(LOWER(FirstCategory) LIKE '%{0}%' OR LOWER(SecondCategory) LIKE '%{0}%' OR LOWER(Description) LIKE '%{0}%' OR LOWER(MFRPart) LIKE '%{0}%') ".format(keyWord)
                    sqlCommand += ") "
                
                firstCondition = True
                if len(footprintData) > 0:
                    sqlCommand += " AND ("
                    for keyWord in footprintData:
                        if not firstCondition:
                            sqlCommand += "AND "
                        firstCondition = False
                    
                        keyWord = keyWord.lower()
                        sqlCommand += "(LOWER(FirstCategory) LIKE '%{0}%' OR LOWER(SecondCategory) LIKE '%{0}%' OR LOWER(Description) LIKE '%{0}%' OR LOWER(MFRPart) LIKE '%{0}%' OR LOWER(Package) LIKE '%{0}%') ".format(keyWord)

                    sqlCommand += ") "
                
                #sqlCommand += "AND Stock > 0 ORDER BY WorstPrice ASC"
                sqlCommand += "ORDER BY LibraryType ASC, CAST(Stock AS INTEGER) DESC"
                
                cur.execute(sqlCommand)
                dbRows = cur.fetchall()
                
                if len(dbRows) > 0:
                    bestGuessRow = dbRows[0]
                    #self.removeCellWidget(row, BomColumnEnum.BOM_COL_PART) 
                    self.bomTable.setCellWidget(rowIndex, BomColumnEnum.BOM_COL_PART, PartAndDatasheetWidget(bestGuessRow[DbRowEnum.DB_ROW_LCSC_PART],'')) 
                    #self.setItem(row, BomColumnEnum.BOM_COL_PART,    LcscLinkLabel(bestGuessRow[DbRowEnum.DB_ROW_LCSC_PART]))
                    
                    if bestGuessRow[DbRowEnum.DB_ROW_LIB_TYPE] == 'Basic':
                        typeMarker = 'Y'
                    else:
                        typeMarker = 'N'
                    self.bomTable.setItem(rowIndex, BomColumnEnum.BOM_COL_BASIC,   QTableWidgetItem(typeMarker))
                    
                    pricePer = round(bestGuessRow[DbRowEnum.DB_ROW_WORST_PRICE]/bestGuessRow[DbRowEnum.DB_ROW_MIN_QUANTITY],4)
                    self.bomTable.setItem(rowIndex, BomColumnEnum.BOM_COL_PRICE,   QTableWidgetItem(str(pricePer)))
                    self.bomTable.setItem(rowIndex, BomColumnEnum.BOM_COL_STOCK,   QTableWidgetItem(str(bestGuessRow[DbRowEnum.DB_ROW_STOCK])))
                    # todo add image
                    # Green means part found
                    self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_COMMENT).setBackground(QColor("lightgreen"))
                else:
                    # Pink means part not found at JLC
                    self.bomTable.item(rowIndex, BomColumnEnum.BOM_COL_COMMENT).setBackground(QColor("lightpink"))
                QApplication.processEvents()
        self.bomSearchForParts.setText("Search For Parts")

        
    def convertProcedure(self):
        # Abort Mechanism not working, needs a thread
        if self.converting == True:
            self.converting = False
            self.convertNow.setText("Convert To Database")
        else:
            self.converting = True
            self.convertNow.setText("Abort")
            
            self.convertStatus.setText("Converting {0}".format(self.csvFile.currentText()))
            
            try:
                os.remove(self.dbFileName.text())
            except:
                pass
            
            con = sqlite3.connect(self.dbFileName.text())
            cur = con.cursor()
            
            # Create table
            cur.execute('''CREATE TABLE jlc
                           (LCSCPart, FirstCategory, SecondCategory, MFRPart, Package, SolderJoint, Manufacturer, LibraryType, Description, Datasheet, Price, Stock, worstPrice, minQuantity, image)''')
            
            # This is naff, csv.reader has no method for getting the number of records so you have to parse twice!!
            with open(self.csvFile.currentText(), encoding='ISO8859') as csvFile:
                row_count = sum(1 for line in csvFile)
                
            with open(self.csvFile.currentText(), encoding='ISO8859', newline='') as csvFile:
                reader = csv.reader(csvFile,delimiter=',')            
    
                rowIndex = 0;
                self.progressBar.setValue(0)                
                self.converting = True
    
                for row in reader:
                    # Abort mechanism
                    if not self.converting == False:
                        imageFilename = ''
                        
                        # The first line in JLC files is a header
                        if len(row) == 13:
                            if self.cacheAllImages.isChecked():
                                imageFilename = row[DbRowEnum.DB_ROW_LCSC_PART] + '.jpg'
                                if imageFilename not in self.currentImageList and imageFilename not in self.failedPartsList:
                                    imageFilename = getimageFilename(row, self.failedPartsList)
                                else:
                                    imageFilename = defaultImage
                                
                            prices = row[DbRowEnum.DB_ROW_PRICE].split(',')
                            worstPrice = 0.0
                            thisPrice = 0.0
                            minQuantity = 99999999
                            for price in prices:
                                # Boil down lists of prices to be just the highest price (usually lowest number)
                                priceFor = price.split(':')
                                
                                if len(priceFor) > 1:
                                    pricePart = priceFor[1]
                                    thisQuantity = int(priceFor[0].split('-')[0])
                                else:
                                    # Not a range of prices
                                    pricePart = price
                                    thisQuantity = 1
                
                                try:
                                    thisPrice = float(priceFor[1])
                                except:
                                    # Sometimes the price is nonsense or omitted
                                    thisPrice = 99999999
                                
                                # Record the price for the minimum quantity
                                if thisPrice > worstPrice:
                                    worstPrice = thisPrice
                                    
                                if thisQuantity <= 1:
                                    minQuantity = 1
                                elif thisQuantity < minQuantity:
                                    minQuantity = thisQuantity
                            
                            row[DbRowEnum.DB_ROW_WORST_PRICE] = worstPrice * minQuantity
                            row[DbRowEnum.DB_ROW_FIRST_CAT] = self.fixUpOddChars(row[DbRowEnum.DB_ROW_FIRST_CAT])
                            row[DbRowEnum.DB_ROW_SEC_CAT] = self.fixUpOddChars(row[DbRowEnum.DB_ROW_SEC_CAT])
                            row[DbRowEnum.DB_ROW_DESCR] = self.fixUpOddChars(row[DbRowEnum.DB_ROW_DESCR])
                            
                            row.append(minQuantity)
                            row.append(imageFilename)
                            cur.execute("INSERT INTO jlc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
                            
                            rowIndex += 1
    
                            self.progressBar.setValue(1 + int((rowIndex*10000)/row_count))
                            QApplication.processEvents()
                            
            self.converting = False
            self.convertNow.setText("Convert To Database")
            self.convertStatus.setText("Done")
                        
            # Save changes
            con.commit()
            con.close()
    
    def openLink(self, linkStr):
        QDesktopServices.openUrl(QUrl(linkStr.replace('%3d','=')))
        
    def handleDb(self):        
        if not os.path.isfile(self.dbFileName.text()):
            error_dialog = QErrorMessage()
            error_dialog.showMessage('Can\'t find database file: {0}'.format(self.dbFileName.text()))
            error_dialog.exec_()
        else:
            self.con = sqlite3.connect(self.dbFileName.text())
    
            cur = self.con.cursor()
    
            sqlCommand = "SELECT * FROM jlc WHERE "
            if not self.useExtendedCheckBox.isChecked():
                sqlCommand += "LibraryType='Basic' AND "
            
            firstCondition = True
            keyWordList = self.keywords.text().split()
    
            if len(keyWordList) > 0:
                firstKeyword = keyWordList[0].upper()
                if len(keyWordList) == 1 and firstKeyword[0] == 'C' and firstKeyword[1:].isnumeric():
                    sqlCommand += "(LCSCPart = '{0}')".format(firstKeyword)
                else:
                    sqlCommand += "("
                    for keyWord in keyWordList:
                        if not firstCondition:
                            sqlCommand += "AND "
                        firstCondition = False
                        
                        keyWord = keyWord.lower()
                        sqlCommand += "(LOWER(FirstCategory) LIKE '%{0}%' OR LOWER(SecondCategory) LIKE '%{0}%' OR LOWER(Description) LIKE '%{0}%' OR LOWER(MFRPart) LIKE '%{0}%') ".format(keyWord)
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
                    sqlCommand += "AND Stock > 0 ORDER BY LibraryType ASC, CAST(Stock AS INTEGER) DESC"
                elif self.sortValue == SortEnum.SORT_PRICE_UP:
                    sqlCommand += "ORDER BY LibraryType ASC, WorstPrice ASC"
                elif self.sortValue == SortEnum.SORT_IN_STOCK_PRICE_UP:
                    sqlCommand += "AND Stock > 0 ORDER BY LibraryType ASC, WorstPrice ASC"
        
                #print(sqlCommand)
                            
                cur.execute(sqlCommand)
    
                rows = cur.fetchall()
                self.update.setText("Searching")
                QApplication.processEvents() 
                self.partTable.searchPopulate(rows, self.loadImages.isChecked())
                self.update.setText("Update")
    
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

