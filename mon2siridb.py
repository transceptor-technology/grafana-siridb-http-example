#!/usr/bin/python3
"""Monitor some data and send records to SiriDB

when:  2017-07-21
by: Jeroen van der Heijden <jeroen@transceptor.technology>
"""

import psutil
import time
import argparse
import asyncio
import socket
import logging
from siridb.connector import SiriDBClient


logging.basicConfig(level=logging.DEBUG)


def adddata(data, prefix, ts, func, *args, props=None, **kwargs):
    f = getattr(psutil, func)
    d = f(*args, **kwargs)

    if not isinstance(d, dict):
        d = {'total': d}

    for k, v in d.items():
        if props is None:
            data["{}{}_{}".format(prefix, k, func)] = [[ts, v]]
        else:
            for p in props:
                data["{}{}_{}_{}".format(prefix, k, func, p)] = \
                    [[ts, getattr(v, p)]]


def getts(time_precision):
    return {
        's': lambda t: int(t),
        'ms': lambda t: int(t * 10**3),
        'us': lambda t: int(t * 10**6),
        'ns': lambda t: int(t * 10**9)
    }[time_precision](time.time())


async def monitor(cluster, args):
    await cluster.connect()

    count = args.number_of_samples if args.number_of_samples else -1;
    prefix = args.prefix.replace('%HOSTNAME%', socket.gethostname())

    try:
        while count:
            data = {}
            ts = getts(args.time_precision)
            
            adddata(data, prefix, ts, 'cpu_percent', interval=args.interval)
            adddata(data, prefix, ts, 'virtual_memory', props=[
                'available',
                'free',
                'percent'])
            adddata(data, prefix, ts, 'disk_usage', '/', props=[
                'total',
                'used',
                'free',
                'percent'])

            adddata(data, prefix, ts, 'disk_io_counters', perdisk=True, props=[
                'read_count',
                'write_count',
                'read_bytes',
                'write_bytes',
                'read_time',
                'write_time'])
            adddata(data, prefix, ts, 'net_io_counters', pernic=True, props=[
                'bytes_sent',
                'bytes_recv',
                'packets_sent',
                'packets_recv',
                'errin',
                'errout',
                'dropin',
                'dropout'])

            logging.info('Inserting {} series...'.format(len(data)))
            await cluster.insert(data)
            await asyncio.sleep(args.interval)
            count -= 1
    finally:
        cluster.close()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-u', '--user',
        type=str,
        default='iris',
        help='username')

    parser.add_argument(
        '-p', '--password',
        type=str,
        default='siri',
        help='password')

    parser.add_argument(
        '-d', '--database',
        type=str,
        default='dbtest',
        help='database name')

    parser.add_argument(
        '-s', '--servers',
        type=str,
        default='localhost:9000',
        help='siridb server(s)')

    parser.add_argument(
        '--prefix',
        type=str,
        default='%HOSTNAME%|',
        help='metrix prefix')

    parser.add_argument(
        '-n', '--number-of-samples',
        type=int,
        default=5,
        help='number of samples. (when 0 the script will run forever)')

    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=1,
        help='interval')

    parser.add_argument(
        '-t', '--time-precision',
        default='s',
        choices=['s', 'ms', 'us', 'ns'],
        help='time precision')

    args = parser.parse_args()

    cluster = SiriDBClient(
        username='iris',
        password='siri',
        dbname='dbtest',
        hostlist=[server.split(':') for server in  args.servers.split(',')])

    loop = asyncio.get_event_loop()
    loop.run_until_complete(monitor(cluster, args))