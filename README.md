# JLCQT
A PYQT5 based search tool for parts on JLCPCB

## Work In Progress
This is a quick and dirty hack which I may decide to revisit. Do, please, feel free to take this and fix it if you have the energy!

## Acknowledgement
Although implemented in a totally different way, this was inspired by https://github.com/yaqwsx/jlcparts.

Until yaqwsx published his web-based tool, I hadn't even thought to try to improve on the clunky web-based search engine that is standard from JLCPCB.com

In many ways, this "App" type tool is inferior having less functionality and less flexibility but... it's quicker for the type of use I wanted.

## Use
This was written with Python3 and uses pyqt5, csv, sqlite3 and requests

It requires a "imageCache" directory in the same directory as the script and that "imageCache" must contain a no_image.png (the one checked in here came from https://commons.wikimedia.org/wiki/File:Error.svg).

Before you start you must get a CSV data file from JLC (https://jlcpcb.com/componentSearch/uploadComponentInfo). This file is updated frequently with current stock etc. Unfortunately, I found downloading this file a bit hit-and-miss (often times out with network errors) so I gave up trying to integrate that into the process. The CSV file is about 13M Bytes at the moment.

Start as:
  python jlcqt.py

Images are cached into imageCache and any parts that don't have images on LCSC are added to the file "failedParts.txt". I've included mine because it has a LOT of failed parts detected and greatly speeds up scanning!

Part images are automatically cached when encountered (or their numbers added to failedParts if there is no image).... BUT this is slow!

Eg: searching for all 10nf capacitors in extended parts took 20 minutes to get all the images - each image takes about 1s to find. Once cached, the DB search took only 13 seconds.

There are 2 tabs:

### Convert Tab
The convert tab will come up if the current directory doesnt have a database file. It lets you:

1) Specify the name of the CSV file (which you must download from https://jlcpcb.com/componentSearch/uploadComponentInfo
2) Option to pre-cache all the images
3) Clear the list of failedParts if it's got errors in it
4) Set the database name (sorry, must be jlc.pcb at the moment)

Hit the "Convert To Database" button to start. Hit the "Abort" button to give up.

### Search Tab
If there is a database in place, the Search tab will appear automatically.

Enter a list of space separated keywords and click the "Update" button.

Eg: cap 10nf

By default it will list entries ordered by largest stock holding, but you can change this to sort by rising-price or by rising-price for in-stock items only.

Sorry, not a full set of options but I'm open to requests... also it is just some python so if you want to tinker...  

## Problems
The code is, er, "alpha-quality". Again, sorry!

There is a considerable amount of poor-practice throughout! I hesitate to publish but one person (you know who you are) wanted to get started with it so... (hangs head in shame).

The Abort operations are very flakey - it needs to grow some threading to allow aborts to take place smoothly and with screen updates. For now, clicking an abort button will, usually, sometimes result in the abort happening after a few seconds.

I think there may be a problem with the get requests as they are astoundingly slow!

I'm not entirely sure about the implicit AND between each keyword, but it seems to cover my personal use case.

I'm not quite comfortable with "sizing" in QT yet so it doesn't stretch in a natural way when you resize it.
