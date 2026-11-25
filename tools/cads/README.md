---
title: "Copernicus Atmosphere Data Store (ADS)"
date: 2026-08-26
draft: false
weight: 1
---
# Copernicus Atmosphere Data Store (ADS)

This tool allows you to retrieve [Copernicus Atmosphere Data Store (ADS)](https://ads.atmosphere.copernicus.eu/cdsapp#!/home).

- Any user willing to use this tool needs to [create a new account](https://ads.atmosphere.copernicus.eu/user/register?destination=/).
- Compose your request directly on ADS and copy/paste it in the input field "Request"
- Users need to add their ADS API Key to Galaxy (see below). Documentation on where to get the ADS API key can be found [here](https://ads.atmosphere.copernicus.eu/api-how-to).
- Be aware that for being able to download dataset from ADS, users also need to agree to their term of use (Licence to use Copernicus Products) on the ADS website.

## Set up user credentials on Galaxy

To enable users to set their credentials and provide their ADS API Key for this tool,
make sure the file `config/user_preferences_extra.yml` has the following section:

```
    cads_account:
        description: Your Copernicus ADS API Key (Copernicus Atmosphere Data Store API Key)
        inputs:
            - name: cads_apikey
              label: Copernicus ADS API Key
              type: password
              required: True
```

