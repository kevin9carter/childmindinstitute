#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#  Copyright 2013 Kitware Inc.
#
#  Licensed under the Apache License, Version 2.0 ( the "License" );
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################

import cherrypy
import datetime

from .model_base import Model, ValidationException
from girder.utility import assetstore_utilities


class File(Model):
    """
    This model represents a File, which is stored in an assetstore.
    """
    def initialize(self):
        self.name = 'file'
        self.ensureIndices(
            ['itemId', 'assetstoreId', 'exts'] +
            assetstore_utilities.fileIndexFields())

    def remove(self, file, updateItemSize=True):
        """
        Use the appropriate assetstore adapter for whatever assetstore the
        file is stored in, and call deleteFile on it, then delete the file
        record from the database.

        :param file: The file document to remove.
        :param updateItemSize: Whether to update the item size. Only set this
        to False if you plan to delete the item and do not care about updating
        its size.
        """
        if file.get('assetstoreId'):
            assetstore = self.model('assetstore').load(file['assetstoreId'])
            adapter = assetstore_utilities.getAssetstoreAdapter(assetstore)
            adapter.deleteFile(file)

        item = self.model('item').load(file['itemId'], force=True)
        self.propagateSizeChange(item, -file['size'], updateItemSize)

        Model.remove(self, file)

    def download(self, file, offset=0, headers=True):
        """
        Use the appropriate assetstore adapter for whatever assetstore the
        file is stored in, and call downloadFile on it. If the file is a link
        file rather than a file in an assetstore, we redirect to it.
        """
        if file.get('assetstoreId'):
            assetstore = self.model('assetstore').load(file['assetstoreId'])
            adapter = assetstore_utilities.getAssetstoreAdapter(assetstore)
            return adapter.downloadFile(file, offset=offset, headers=headers)
        elif file.get('linkUrl'):
            if headers:
                raise cherrypy.HTTPRedirect(file['linkUrl'])
            else:
                def stream():
                    yield file['linkUrl']
                return stream
        else:  # pragma: no cover
            raise Exception('File has no known download mechanism.')

    def validate(self, doc):
        if doc.get('assetstoreId') is None:
            if 'linkUrl' not in doc:
                raise ValidationException(
                    'File must have either an assetstore ID or a link URL.',
                    'linkUrl')
            doc['linkUrl'] = doc['linkUrl'].strip()

            if not doc['linkUrl'].startswith(('http:', 'https:')):
                raise ValidationException(
                    'Linked file URL must start with http: or https:.',
                    'linkUrl')
        if 'name' not in doc or not doc['name']:
            raise ValidationException('File name must not be empty.', 'name')

        doc['exts'] = doc['name'].split('.')[1:]

        return doc

    def createLinkFile(self, name, parent, parentType, url, creator):
        """
        Create a file that is a link to a URL rather than something we maintain
        in an assetstore.
        :param name: The local name for the file.
        :type name: str
        :param parent: The parent object for this file.
        :type parent: folder or item
        :param parentType: The parent type (folder or item)
        :type parentType: str
        :param url: The URL that this file points to
        :param creator: The user creating the file.
        :type user: user
        """
        if parentType == 'folder':
            # Create a new item with the name of the file.
            item = self.model('item').createItem(
                name=name, creator=creator, folder=parent)
        elif parentType == 'item':
            item = parent

        file = {
            'created': datetime.datetime.now(),
            'itemId': item['_id'],
            'creatorId': creator['_id'],
            'assetstoreId': None,
            'name': name,
            'linkUrl': url
        }

        try:
            file = self.save(file)
            return file
        except ValidationException:
            if parentType == 'folder':
                self.model('item').remove(item)
            raise

    def propagateSizeChange(self, item, sizeIncrement, updateItemSize=True):
        """
        Propagates a file size change (or file creation) to the necessary
        parents in the hierarchy. Internally, this records subtree size in
        the item, the parent folder, and the root node under which the item
        lives. Should be called anytime a new file is added, a file is
        deleted, or a file size changes. Uses an update command with $inc to
        allow the DBMS to atomically update size info.

        :param item: The parent item of the file.
        :type item: dict
        :param sizeIncrement: The change in size to propagate.
        :type sizeIncrement: int
        :param updateItemSize: Whether the item size should be updated. Set to
        False if you plan to delete the item immediately and don't care to
        update its size.
        """
        if updateItemSize:
            # Propagate size up to item
            self.model('item').update(query={
                '_id': item['_id']
            }, update={
                '$inc': {'size': sizeIncrement}
            }, multi=False)

        # Propagate size to direct parent folder
        self.model('folder').update(query={
            '_id': item['folderId']
        }, update={
            '$inc': {'size': sizeIncrement}
        }, multi=False)

        # Propagate size up to root data node
        self.model(item['baseParentType']).update(query={
            '_id': item['baseParentId']
        }, update={
            '$inc': {'size': sizeIncrement}
        }, multi=False)

    def createFile(self, creator, item, name, size, assetstore, mimeType):
        """
        Create a new file record in the database.
        :param item: The parent item.
        :param creator: The user creating the file.
        :param assetstore: The assetstore this file is stored in.
        :param name: The filename.
        :type name: str
        :param size: The size of the file in bytes.
        :type size: int
        :param mimeType: The mimeType of the file.
        :type mimeType: str
        """
        file = {
            'created': datetime.datetime.now(),
            'itemId': item['_id'],
            'creatorId': creator['_id'],
            'assetstoreId': assetstore['_id'],
            'name': name,
            'mimeType': mimeType,
            'size': size
        }

        self.propagateSizeChange(item, size)

        return self.save(file)
