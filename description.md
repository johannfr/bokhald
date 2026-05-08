# Bokhald

Personal finanace/accounting software

The default language shall be english, but I want to be able to translate everything
easily using whatever translation system/format that is industry standard and matches
the tech-stack of this application.

## Technical details

### Language and libraries

The software shall be written in Python and a nix flake file with a dev shell needs
to be defined with all the dependecies. The nix flake shall use nixpkgs version 25.11,
NOT unstable.

The user-interface shall be written using NiceGUI. The nix flake shall by default generate
a target that will run the NiceGUI application, which probably involves running an embedded
backend server, and then use the webbrowser module to open up the default browser with
the backend URL.

### Database

We shall use a SQLite database to store the data for this application, and an ORM, to
map the database into Python classes. Preferably SQLAlchemy.

The ORM shal be SQLAlchemy.

## General requirements

### Accounts

The software nedds to support multiple accounts, but for now only one account type. I want
to be able to set an initial balance on this account when it is created.

### Payment methods/types

I want to register different methods of payments. Each one shall have a name and a
description and an optional URL to open the subscriptions overview for each vendor.

The default list shall be:

- Krafa (this is a standard Icelandic bill, that is issued through Reiknistofa bankanna)
- Automatic transfer
- Credit card
- Paypal
- Google Play

### Subscriptions/bills/payments

I want to register recurring subscriptions or transactions to this system, and choose
which account will be used to pay each one.
They shall have a name, a description, estimated amount, day of month, and recurrance. Some subscriptions
or payments are only paid during certain months, so this needs to be registered and parsed
in a similar manner as pages are often represented in print-dialogs: Comma separated list
of month numbers, a range of month numbers, and a mix of comma separated list of month numbers
and ranges of month numbers.
I also want to be able to set up internal transactions, which shall be double entry, so I can
set up scheduled payments between my own accounts and see their balance over time.

### Estimates

This system needs to give me an estimate, for each account, how much money needs to be
transferred every month to make sure the balance of the account never goes below zero.
It would also be nice to be able to configure a safety-margin for each account, probably
as a percentage, to make sure we don't enter a danger zone.

### Tracking

For each monthly transaction that occurs, I want to be able to register and track the
actual amount that I paid for each subscription/bill for that month. Since I mentioned that some of those
would have an estimated amount, I want to track what the actual amount was. This applies
to things like electric bills and other consumables, where the final amount isn't known
exactly beforehand.

## User Interface

The default view of this system shall be a table for an account, similar to a spreadsheet table. The months
shall be represented in columns, the year in a cell above the months that spans the width
of the months of that year. Each row contains each subscription/bill/transaction with an amount for each month.
The monthly injection payments needed for each account shall also be there, as a positive number, and bills shall be negative.
I wont the montly injection to be at the top of the table.

The current month shall be at the center of the view and I want to be able to scroll horizontally to
see other months and years that are not visible initially. I think scrolling two years into the future is enough, but
scrolling to the very beginning of data is required. If lazy-loading is easy with NiceGUI, let's do that.
