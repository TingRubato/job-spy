# Job-Spy

## Description

This is a python project that allows users to search for jobs from indeed. It is built with the PostgreSQL and [Selenium](https://selenium.dev) library to scrape job postings from job boards. The scraped data is then stored in a PostgreSQL database and is served to the user via a REST API (In progress, refer to [server.js](https://raw.githubusercontent.com/TingRubato/EZZY-Job/main/server/server.js)). 

The user can then search for jobs and filter job postings by location, job title, and company name. The user can also save job postings to their account and apply to them later. Additionally, a dashboard is provided to the user to view their saved jobs and their application status using Grafana.


## Table of Contents

- [Job-Spy](#job-spy)
  - [Description](#description)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

## Installation

To install this project, follow these steps: the easiest way to install this project is to use Docker. If you do not have Docker installed, please follow the instructions [here](https://docs.docker.com/get-docker/).

## Usage

To use this project, follow these steps:

1. Pull the source code from the repository.
2. Make a copy of the `.env.example` file located in the `./config` directory.
3. Rename the copied file to `.env`.
4. Run `docker-compose up` to start the project.

## Contributing

Thank you for considering contributing to this project! To get started, please follow these guidelines:

1. Fork the repository and create your branch.
2. Make your changes and commit them.
3. Submit a pull request.

## License

This project is licensed under the MIT License. For more information, please see the [LICENSE](/path/to/license) file.

For any further questions or inquiries, you can contact me at ting.x@wustl.edu.