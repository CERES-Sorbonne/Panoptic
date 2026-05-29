
# dataStore2

negative ids for computed properties dont exist anymore
use the system_key for special treatment
Columns should be filled like any other property

interface SlotInitData {

id: number

sha1: string

folderId: number

width: number

height: number

}

we dont need this i think. Init should be just per array. Only the ids are needed at first.

Then it depends on what is requested by the filters.
everything is columns


Focus only on the dataStore.ts and dataStore2.ts files. Make the dataStore complete and dont care about possible connection for now or compability with the managers.

