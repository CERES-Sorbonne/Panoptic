DELETE FROM instance_property_values WHERE 1=1;
DELETE FROM image_property_values WHERE 1=1;
DELETE FROM tags WHERE 1=1;
DELETE FROM properties WHERE 1=1;
DELETE FROM tabs WHERE 1=1;
INSERT INTO tabs VALUES (0, "Tab", '{"name": "Tab",
"display": "tree",
"filter": {
    "depth": 0,
    "filters": [],
    "groupOperator": "and",
    "isGroup": true
},
"groups": [],
"sortList": [],
"imageSize": 100,
"visibleProperties": {},
"visibleFolders": {},
"selectedFolders": {},
"propertyOptions": {}
}');