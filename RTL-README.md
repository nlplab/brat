# RTL Support for brat #

To fix the highlight issues brat has for the RTL languages, we made changes to the scripts to make the
RTL text flow from right margin instead of just look like a LTR text with RTL words. We made use of the
client side scripts of the user @fsalotaibi and his brat [implementation][website].

[website]: http://www.ebsar.com/brat/#/FGANER/109-out

Though this version of brat is not compatible with the master that supports LTR text, we wanted to push it to
help people still looking for a fix to this issue.

## Files with changes from  @fsalotaibi ##
/client/src/ajax.js
/client/src/annotator_ui.js
/client/src/dispatcher.js
/client/src/util.js
/client/src/visualizer.js
/client/src/visualizer_ui.js

All the files with changes are still under MIT License.
