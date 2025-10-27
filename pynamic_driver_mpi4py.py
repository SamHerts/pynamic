import sys, os
import time
end_time = time.time()
start_time = 0
mpi_avail = True
try:
    from mpi4py import MPI as actual_mpi
    class mpi_wrapper:
        def __init__(self):
            self.rank = actual_mpi.COMM_WORLD.Get_rank()
            self.procs = actual_mpi.COMM_WORLD.Get_size()
            self.SUM = actual_mpi.SUM
        def reduce(self, buffer, operation, destination):
            return actual_mpi.COMM_WORLD.reduce(buffer, op=operation, root=destination)
        def barrier(self):
            return actual_mpi.COMM_WORLD.Barrier()
    mpi = mpi_wrapper()
except:
    class dummy_mpi:
        def __init__(self):
            self.rank = 0
            self.procs = 1
        def barrier(self):
            pass
    mpi = dummy_mpi()
    mpi_avail = False

mpi.barrier()
myRank = mpi.rank
nProcs = mpi.procs
if myRank == 0:
    print('Pynamic: Version 1.3.3')
    print('Pynamic: run on %s with %s MPI tasks\\n' %(time.strftime("%x %X"), nProcs))
    if len(sys.argv) > 1:
        start_time = float(sys.argv[1])
        print('Pynamic: startup time = ' + str(end_time - start_time) + ' secs')
    print('Pynamic: driver beginning... now importing modules')

    import_start = time.time()
import libmodulebegin
## START_MODULE_IMPORTS
## END_MODULE_IMPORTS
import libmodulefinal

mpi.barrier()
if myRank == 0:
    import_end = time.time()
    import_time = import_end - import_start
    print('Pynamic: driver finished importing all modules... visiting all module functions')

    call_start = time.time()
libmodulebegin.begin_break_here()
## START_MODULE_CALLS
## END_MODULE_CALLS
libmodulefinal.break_here()
mpi.barrier()
if myRank == 0:
    call_end = time.time()
    call_time = call_end - call_start
    print('Pynamic: module import time = ' + str(import_time) + ' secs')
    print('Pynamic: module visit time = ' + str(call_time) + ' secs')
    print('Pynamic: module test passed!\\n')
if mpi_avail == False:
    sys.exit(0)

if myRank == 0:
    print('Pynamic: testing mpi capability...\\n')
    mpi_start = time.time()

## START_EXAMPLE - If examples need to be modified, do so here
from array import *
from struct import *
# Function to return BMP header
def makeBMPHeader(width, height):
    # Set up the bytes in the BMP header
    headerBytes = [66, 77, 28, 88, 0, 0, 0, 0, 0, 0, 54, 0, 0, 0]
    headerBytes += [40] + 3 * [0] + [100] + 3 * [0] + [75, 0, 0, 0, 1, 0, 24] + [0] * 9 + [18, 11, 0, 0, 18, 11]
    headerBytes += [0] * 10

    data = b''
    for x in range(54):
        data += pack('B', headerBytes[x])

    # Create a string to overwrite the width and height in the BMP header
    replaceString = pack('<I', width)
    replaceString += pack('<I', height)

    # Return a 54-byte string that will be the new BMP header
    newString = data[0:18] + replaceString + data[26:54]
    return newString


# Define our fractal parameters
c = 0.4 + 0.3j
maxIterationsPerPoint = 64
distanceWhenUnbounded = 3.0


# define our function to iterate
def f(x):
    return x * x + c


# Define the bounds of the xy plane we will work in
globalBounds = (-0.6, -0.6, 0.4, 0.4)  # x1, y1, x2, y2

# define the size of the BMP to output
# For now this must be divisible by the # of processes
bmpSize = (400, 400)

# Define the range of y-pixels in the BMP this process works on
myYPixelRange = [0, 0]
myYPixelRange[0] = int(mpi.rank * bmpSize[1] / mpi.procs)
myYPixelRange[1] = int((mpi.rank + 1) * bmpSize[1] / mpi.procs)

if mpi.rank == 0:
    print("Starting computation (groan)\n")

# Now we can start to iterate over pixels!!
myString = ""
myArray = array('B')
for y in range(myYPixelRange[0], myYPixelRange[1]):
    for x in range(0, bmpSize[0]):

        # Calculate the (x,y) in the plane from the (x,y) in the BMP
        thisX = globalBounds[0] + (float(x) / bmpSize[0]) * (globalBounds[2] - globalBounds[0])
        thisY = (float(y) / bmpSize[1]) * (globalBounds[3] - globalBounds[1])
        thisY += globalBounds[1]

        # Create a complex # representation of this point
        thisPoint = complex(thisX, thisY)

        # Iterate the function f until it grows unbounded
        nxt = f(thisPoint)
        numIters = 0
        while 1:
            dif = nxt - thisPoint
            if abs(nxt - thisPoint) > distanceWhenUnbounded:
                break;
            if numIters >= maxIterationsPerPoint:
                break;
            nxt = f(nxt)
            numIters = numIters + 1

        # Convert the number of iterations to a color value
        colorFac = 255.0 * float(numIters) / float(maxIterationsPerPoint)
        myRGB = (colorFac * 0.8 + 32, 24 + 0.1 * colorFac, 0.5 * colorFac)

        # append this color value to a running list
        myArray.append(int(myRGB[2]))  # blue first
        myArray.append(int(myRGB[1]))  # The green
        myArray.append(int(myRGB[0]))  # Red is last

# Now I reduce the lists to process 0!!
masterArray = mpi.reduce(myArray, mpi.SUM, 0)

# Tell user that we're done
# message = "process " + str(mpi.rank) + " done with computation!!"
# print(message)

# Process zero does the file writing
if mpi.rank == 0:
    # Write a BMP header
    myBMPHeader = makeBMPHeader(bmpSize[0], bmpSize[1])
    print("Header length is ", len(myBMPHeader))
    print("BMP size is ", bmpSize)
    print("Data length is ", len(masterArray))

    # Open the output file and write to the BMP
    outFile = open('output.bmp', 'wb')
    outFile.write(myBMPHeader)
    outFile.write(masterArray)
    outFile.close()
# END_EXAMPLE

mpi.barrier()
if myRank == 0:
    mpi_end = time.time()
    print('\\nPynamic: fractal mpi time = ' + str(mpi_end - mpi_start) + ' secs')
    print('Pynamic: mpi test passed!\\n')