# semeval2017-ScienceIE

Development data for SemEval 2017 ScienceIE task (Task 10).
Please contact the task organisers (scienceie@googlegroups.com) if there are any problems with using the data

The data consists of:
* .ann files: standoff annotation files, each line represents an annotation. Format: ID<tab>label<space>start-offset<space>end-offset<tab>surface-form
The offsets represent character offsets based on the .txt files. Note that the evaluation script ignores the IDs and the surface forms and only judges based on the character offsets.
* .txt files: text corresponding to the standoff annotation files
* .xml files: full publications from ScienceDirect in .xml format. Note that the text contained in the .txt files are paragraphs from the .xml files. These files are *not needed* for participating in the challenge. They are included because some teams might want to use them as additional background information. 

## References:
* SemEval task: https://scienceie.github.io/
* .ann format: http://brat.nlplab.org/standoff.html