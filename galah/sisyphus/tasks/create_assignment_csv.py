# Copyright 2012-2013 John Sullivan
# Copyright 2012-2013 Other contributers as noted in the CONTRIBUTERS file
#
# This file is part of Galah.
#
# Galah is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Galah is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Galah.  If not, see <http://www.gnu.org/licenses/>.

import shutil
import subprocess
import os
import datetime
from bson import ObjectId

from galah.db.models import Submission, CSV, TestResult, User, Assignment

# Set up configuration and logging
from galah.base.config import load_config
config = load_config("sisyphus")

import logging
logger = logging.getLogger("galah.sisyphus.create_assignment_csv")

def _create_assignment_csv(csv_id, requester, assignment):
    csv_id = ObjectId(csv_id)

    csv_file = temp_directory = ""

    # Find any expired archives and remove them
    deleted_files = []
    for i in CSV.objects(expires__lt = datetime.datetime.today()):
        deleted_files.append(i.file_location)

        if i.file_location:
            try:
                os.remove(i.file_location)
            except OSError as e:
                logger.warning(
                    "Could not remove expired csv file at %s: %s.",
                    i.file_location, str(e)
                )

        i.delete()

    if deleted_files:
        logger.info("Deleted csv files %s.", str(deleted_files))

    # This is the CSV object that will be added to the database
    new_csv = CSV(
        id = csv_id,
        requester = requester
    )

    temp_directory = csv_file = None
    try:
        assn = Assignment.objects.get(id = ObjectId(assignment))

        # Grab all student users for this class.
        users = list(
            User.objects(
                account_type = "student",
                classes = assn.for_class
            )
        )

        # Form the query
        query = {
            "assignment": ObjectId(assignment),
            "most_recent": True,
            "user__in": [i.id for i in users]
        }

        # Grab the most recent submissions from each user.
        submissions = list(Submission.objects(**query))

        # Create the actual csv file.
        csv_file = open(config["CSV_DIRECTORY"] + str(csv_id), "w")

        for i in submissions:
            score = "None"
            if i.test_results:
                test_result = TestResult.objects.get(id = i.test_results)
                score = str(test_result.score)

            print >> csv_file, "%s,%s,%s" % \
                (i.user, score, i.timestamp.strftime("%Y-%m-%d-%H-%M-%S"))

        csv_file.close()

        new_csv.file_location = config["CSV_DIRECTORY"] + str(csv_id)

        new_csv.expires = \
            datetime.datetime.today() + config["TEACHER_CSV_LIFETIME"]

        new_csv.save(force_insert = True)
    except Exception as e:
        new_csv.file_location = None
        os.remove(config["CSV_DIRECTORY"] + str(csv_id))

        new_csv.error_string = str(e)
        new_csv.save(force_insert = True)

        raise
