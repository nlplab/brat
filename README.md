# brat rapid annotation tool (brat) #

## Documentation ##

In an attempt to keep all user-facing documentation in one place, please visit
the [brat homepage][brat] which contains extensive documentation and examples
of how to use and configure brat. We apologise for only providing minimal
documentation along with the installation package but the risk of having
out-dated documentation delivered to our end-users is unacceptable.

If you find bugs in your brat installation or errors in the documentation,
please file an issue at our [issue tracker][brat_issues] and we will strive to
address it promptly.

[brat]:         http://brat.nlplab.org
[brat_issues]:  https://github.com/nlplab/brat/issues

## About brat ##

*brat* (brat rapid annotation tool) is based on the [stav][stav] visualiser
which was originally made in order to visualise
[BioNLP'11 Shared Task][bionlp_2011_st] data. brat aims to provide an
intuitive and fast way to create text-bound and relational annotations.
Recently, brat has been widely adopted in the community. It has been used to
create well-over 50,000 annotations by the [Genia group][genia] and several
other international research groups for a number of annotation projects.

[stav]:             https://github.com/nlplab/stav/
[bionlp_2011_st]:   http://2011.bionlp-st.org/
[genia]:            http://www.geniaproject.org/

brat aims to overcome short-comings of previous annotation tools such as:

* De-centralisation of configurations and data, causing synchronisation issues
* Annotations and related text not being visually adjacent
* Complexity of set-up for annotators
* Etc.

brat does this by:

* Data and configurations on a central web server (as Mark Twain said:
    "Put all your eggs in one basket, and then guard that basket!")
* Present text as it would appear to a reader and maintain annotations close
    to the text
* Zero set-up for annotators, leave configurations and server/data maintainence
    to other staff

## License ##

brat itself is available under the permissive [MIT License][mit] but
incorporates software using a variety of open-source licenses, for details
please see see LICENSE.md.

[mit]:  http://opensource.org/licenses/MIT

## Citing ##

If you do make use of brat or components from brat for annotation purposes,
please cite the following publication:

    @inproceedings{,
        author      = {Stenetorp, Pontus and Pyysalo, Sampo and Topi\'{c}, Goran
                and Ohta, Tomoko and Ananiadou, Sophia and Tsujii, Jun'ichi},
        title       = {{brat}: a Web-based Tool
                for {NLP}-Assisted Text Annotation},
        booktitle   = {Proceedings of the Demonstrations Session
                at {EACL} 2012},
        month       = {April},
        year        = {2012},
        address     = {Avignon, France},
        publisher   = {Association for Computational Linguistics},
    }

If you make use of brat or its components solely for visualisation purposes,
please cite the following publication:

    @InProceedings{stenetorp2011supporting,
      author    = {Stenetorp, Pontus and Topi\'{c}, Goran and Pyysalo, Sampo
          and Ohta, Tomoko and Kim, Jin-Dong and Tsujii, Jun'ichi},
      title     = {BioNLP Shared Task 2011: Supporting Resources},
      booktitle = {Proceedings of BioNLP Shared Task 2011 Workshop},
      month     = {June},
      year      = {2011},
      address   = {Portland, Oregon, USA},
      publisher = {Association for Computational Linguistics},
      pages     = {112--120},
      url       = {http://www.aclweb.org/anthology/W11-1816}
    }

Lastly, if you have enough space we would be very happy if you also link to
the brat homepage:

    ...the brat rapid annotation tool\footnote{
        \url{http://brat.nlplab.org}
    }

## Contributing ##

As with any software brat is under continuous development. If you have
requests for features please [file an issue][brat_issues] describing your
request. Also, if you want to see work towards a specific feature feel free to
contribute by working towards it. The standard procedure is to fork the
repository, add a feature, fix a bug, then file a pull request that your
changes are to be merged into the main repository and included in the next
release. If you seek guidance or pointers please notify the brat developers
and we will be more than happy to help.

If you send a pull request you agree that the code will be distributed under
the same license as brat (MIT). Additionally, all non-anonymous contributors
are recognised in the CONTRIBUTORS.md file.

## Contact ##

For help and feedback please contact the authors below, preferably with all on
them on CC since their responsibilities and availability may vary:

* Goran Topić       &lt;goran is s u-tokyo ac jp&gt;
* Sampo Pyysalo     &lt;smp is s u-tokyo ac jp&gt;
* Pontus Stenetorp  &lt;pontus is s u-tokyo ac jp&gt;
