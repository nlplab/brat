---
layout: base
title:  "Service Integration"
---

# {{ page.title }} #

As of version v1.3 (Crunchy Frog) brat supports the integration of tagging
services for tools such as [CoreNLP][corenlp] or [NERsuite][nersuite].
A tagging service is a web-service that speaks the brat tagging service
protocol (don't worry, it isn't as fancy as it sounds).
What you do is implement a tagger service in your language of choice
(`tools/randomtaggerservice.py` is a great example on how this can be done),
you then configure the server to communicate with your tagger service using
HTTP (thus you can place the service on a server instead of your local machine).

[corenlp]: http://nlp.stanford.edu/software/corenlp.shtml
[nersuite]: http://nersuite.nlplab.org/

## Server Configuration ##

Tagging services are configured in `tools.conf`, service entries should be
made in the `annotators` section.
Please see the examples in `tools.conf` for further details.

## Tagging Service Protocol ##

The following section describes the brat server and expected tagging service
behaviour.

### Request ###

At any time the server may issue a POST request to the tagging service, it
will have a body containing the document text (`text/plain; charset=utf-8`)
that is expected to be processed by the tagging service.

### Response ###

The response is of type `application/json` and uses the following form:


    // The main structure is a dictonary
    {
        // With id entries, these can be anything as they are discared by the
        //  server and their main purpose is for error reporting
        "0": {
            // Annotation type, such as "Company", "Protein", etc.
            "type": "Dead-parrot",
            // Tag offsets, currently only supports a single offset pair
            "offsets": [[0, 15]],
            // Tag texts for each offset, currently only supports a single text
            "texts": ["Norwegian Blue"]
        },
        // Additional entries go here
        ...
    }

If no annotations are found, or for testing purposes, simply return an empty
dictionary.
