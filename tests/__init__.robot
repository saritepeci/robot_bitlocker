*** Settings ***
Documentation       Root suite for the BitLocker + Smart Card Windows authentication
...                 test estate. This __init__ runs ONCE for the whole directory and
...                 is the single place that bootstraps the framework. Child suites
...                 declare their own preconditions via the state facades, so they
...                 remain runnable in isolation too.
Metadata            Framework       Robot BitLocker Reference Architecture
Metadata            Backend         Configured via ROBOT_ENVIRONMENT (default: 'default')
Resource            ../resources/common/settings.resource
Suite Setup         Initialize Test Framework
