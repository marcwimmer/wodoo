#!/bin/bash
subject=$(date)
echo "$subject" | mail -s "$subject" franz.wimmer@conpower.de
