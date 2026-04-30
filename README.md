# iCalendar API integration for Home Assistant
Generates an iCalendar (.ics) link that you can use to view your Home Assistant calendars in another app.

## Installation
### HACS (recommended)
1. [Install HACS](https://hacs.xyz/docs/setup/download), if you did not already
2. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=chris-y&repository=ha-icalendar&category=integration)
3. Press the Download button
4. Add the following to your configuration.yaml file:

   ```
   icalendar:
     calendars:
       - entity_id: calendar.entity_id
         secret: yourSuperSecret
   ```

There should be a "calendars" entry for all calendars that need remote access.

5. Restart Home Assistant

### Manually
Copy all files in the *custom_components/icalendar* folder to your Home Assistant folder *config/custom_components/icalendar*.

## Getting started
In your preferred calendar application, input your iCalendar URL in the following format:

- Home Assistant URL - http://homeassistant.local:8123
- iCalendar API path - /api/ics/
- Calendar Entity Id - calendar.*entity_id*
- Secret parameter - ?s=*secret*

### Example

- http://*homeassistant.local:8123*/api/ics/calendar.*holidays*?s=*yourSuperSecret*

## Additional configuration

You can add colours to both calendars and specific named events by adding them to your config.
Colours are specified as [named CSS3 colours](https://developer.mozilla.org/en-US/docs/Web/CSS/named-color).
For example, to colour events for your bin calendar, you might use:

```
icalendar:
  calendars:
    - entity_id: calendar.bins
      secret: yourSuperSecret
      colour: black
  colours:
    - name: "Recycling"
      colour: green
    - name: "Food waste"
      colour: brown
```

This will colour the event "Recycling" as green, "Food waste" as brown and the calendar itself (usually this is used as the default event colour) as black.

## Known issues
- Line length is not restricted to 75 characters

## Future enhancements
Your support is welcomed.
