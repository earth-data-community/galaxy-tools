---
title: Contributing to Galaxy for Earth System Sciences
slug: "Contribute to GESS"
weight: 2
tags: ["tools", ""wrappers, "workflow"]
---

# Contributing

This document describes how to contribute to this repository. Pull
requests containing bug fixes, updates, and extensions to the existing
tools and tool suites in this repository will be considered for
inclusion.

## How to Contribute

* Make sure you have a [GitHub account](https://github.com/signup/free)
* Make sure you have git [installed](https://docs.github.com/en/get-started/git-basics/set-up-git)
* Fork the repository on [GitHub](https://github.com/earth-data-community/galaxy-tools/fork)
* Make the desired modifications - consider using a [feature branch](https://github.com/Kunena/Kunena-Forum/wiki/Create-a-new-branch-with-git-and-manage-branches).
* Make sure you have added the necessary tests for your changes and they pass.
* Make sure submitted tools meet IUC [Best Practices](https://galaxy-iuc-standards.readthedocs.io/en/latest/best_practices/tool_xml.html)
* Open a [pull request](https://docs.github.com/en/pull-requests/reference/pull-requests)
  with these changes.

## What to contribute

* Wrappers for new [OSI-approved licensed](https://opensource.org/licenses) tools
* Visualization Plugins
* Updates for tools
* Enhancements for tools (e.g. supporting new parameters)
* Bug fixes
* Documentation improvements
* New test cases

### Abandoned Tools

* For tools of general interest, the Earth Data community is usually willing to adopt tools that
  you (the developer) are abandoning.
* If there are tools that you find useful but seem to be abandoned and not
  updated, you're welcome to create an issue recommending that the Earth Data community adopt
  that tool.

## What not to contribute

* Things already wrapped and currently maintained by other users
* Wrappers without tests
* New datatypes. These should be added directly to the [Galaxy codebase](https://github.com/galaxyproject/galaxy).

## Tests

All contributed tools should include test cases. They need not
necessarily cover all uses of the program, but should ensure that it is
generally working. The Galaxy Hub has a
[page](https://galaxyproject.org/admin/tools/writing-tests/) on writing
tests.

The IUC and the Earth Data community strongly recommend testing with [planemo](https://github.com/galaxyproject/planemo/), which provides a simple command line utility for testing functionality

```console
$ planemo test --install_galaxy my_tool.xml
```

## Requirements for Contributions

Before a PR will be accepted, the reviewers will check some requirements such as [some requirements](https://galaxy-iuc-standards.readthedocs.io/) on the
submitted code (which we will be happy to help you achieve if you need the
assistance).

* Continuous integration tests must pass: 
    * The tests must pass (`planemo test --install_galaxy my_tool.xml`)
    * The tools must pass linting by planemo (`planemo lint my_tool.xml`)
    * Any Python or R script must pass linting with `flake8` and `styler`, respectively
* If there's a relevant paper for the tool, it should be cited in a [citation](https://docs.galaxyproject.org/en/latest/dev/schema.html#tool-citations) block
* The tool must be licensed to allow use by anyone. The OSI maintains a [list of appropriate licenses](https://opensource.org/licenses)
* At least one approving review by an Earth data admin or an IUC member

## Develop a tool 

Best practices for developing new tools are IUC [Best Practices](https://galaxy-iuc-standards.readthedocs.io/en/latest/best_practices/tool_xml.html)

- Always use quotes for tool directory (python '$__tool_directory__/psymap_simple.py') and tool parameters (--cmap '$adv.colormap')
- When wrapping an existing underlying tool, use the same version than the underlying tool
- `from_work_dir` will tell Galaxy to pick this file, this saves you the cp/mv command in the command section:

~~~`bash`
<data name="ofilename" format="png" from_work_dir="image.png"/>
~~~

- If the output format depends on the type of output file, try to avoid `auto_format` and use `change_format` instead:

~~~`bash`
<data name="ofilename" format="json">
                <change_format>
                    <when input="format" value="csv" format="csv" />
~~~               

- Add [EDAM](https://ifb-elixirfr.github.io/edam-browser) ontology in your tool, for both topics and operations. Most climate tools will have:

~~~`bash`
<edam_topics>
  <edam_topic>topic_3855</edam_topic>
  <edam_topic>topic_3318</edam_topic>
</edam_topics>
~~~               

- [Environmental science](https://ifb-elixirfr.github.io/edam-browser/#topic_3855) (topic 3855)
- [Physics](https://ifb-elixirfr.github.io/edam-browser/#topic_3318) (topic_3318)


- If you are using [firefox](https://www.mozilla.org/en-GB/firefox/all/#product-desktop-release), you can install [EDAM Popovers plugin](https://addons.mozilla.org/en-US/firefox/addon/edam-popovers/) to get the detailed information to EDAM terms.

![EDAM popovers](edam_popovers.png)

We may need to update all the tools later when additional topics will be added for geosciences.
