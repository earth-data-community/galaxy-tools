---
title: "Copernicus Climate Data Store (C3S)"
date: 2026-08-26
draft: false
weight: 1
---
# Copernicus Climate Data Store (C3S)

This tool allows you to retrieve [Copernicus Climate Data Store (C3S)](https://cds.climate.copernicus.eu/#!/home).

- Any user willing to use this tool needs to [create a new account](https://cds.climate.copernicus.eu/user/register?destination=%2F%23!%2Fhome).
- Compose your request directly on C3S and copy/paste it in the input field "Request"
- Users need to add their CDS API Key to Galay (see below). Documentation on where to get the CDS API key can be found [here](https://cds.climate.copernicus.eu/api-how-to).
- Be aware that for being able to download dataset from C3S, users also need to agree to their term of use (Licence to use Copernicus Products) on the C3S website.

## Set up user credentials on Galaxy

To enable users to set their credentials and provide their CDS API Key for this tool,
make sure the file `config/user_preferences_extra.yml` has the following section:

```
    c3s_account:
        description: Your CDS API Key (Copernicus Climate Change Service API Key)
        inputs:
            - name: c3s_cds_apikey
              label: C3S CDS API Key
              type: text
              required: True
```

