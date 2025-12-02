"""這個模組是測試用的"""

#這是第一個function
def firstFun(theList,indent=False,level=0):
    for aa in theList:
        if isinstance(aa,list):
            firstFun(aa,indent,level+1)
        else:
            if indent:
                for tab_stop in range(level):
                    print("\t",end='')
            print(aa)

