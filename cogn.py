from multiprocessing import Process
from multiprocessing.connection import Listener, Client
import numpy as np
import time
import json
import platform
import argparse


def sender(address, noisy_mode):

    with Listener(address) as listener:
        with listener.accept() as conn:
            try:
                # Using "time.perf_counter" for highest resolution
                next_send = time.perf_counter()
                
                # Noise may start at anytime within the first 3s
                next_drop = next_send + np.random.default_rng().uniform(0.01, 3)

                # "time.sleep" isn't accurate enough:
                # - Uses "time.monotonic" which is significantly less precise
                # - Actual sleep time may be less/more than requested
                
                # Looping without sleeping produces the most accurate and stable frequency
                # but may saturate the CPU. I'm assuming multicore here. For single core
                # I'd conceder adding a short sleep.

                while True:
                    if time.perf_counter() >= next_send:
                        # print("elapsed:", time.perf_counter() - next_send)
                        if noisy_mode and next_send >= next_drop:
                            next_drop = next_send + np.random.default_rng().uniform(2, 3)
                            print("\t****  noise  ****", flush=True)
                        else:
                            vec = np.random.default_rng().normal(size=50)
                            conn.send(vec)
                        
                        # "next_send=time.perf_counter()" would result in an upward drift
                        next_send += 0.001

            except (KeyboardInterrupt, IOError):
                pass


def receiver(address, noisy_mode, series_size):
    metrix_size = 100
    expected_rate = 0.001
    rates = []
    vectors = []

    with Client(address) as conn:
        try:
            prev_recv_time = None
            prev_drop_time = None
            drops = 0

            while len(vectors) < series_size * metrix_size:
                vec = conn.recv()
                recv_time = time.perf_counter()

                # setting initial rate to expected_rate
                if prev_recv_time is None:
                    rate = expected_rate
                    prev_drop_time = recv_time
                else:
                    rate = recv_time - prev_recv_time
                
                if noisy_mode and rate > 1.8 * expected_rate and len(vectors) > 10:
                    print(f'\nWARNING: packet dropped (waited {rate - expected_rate}s). ', end='', flush=True)
                    if drops:
                        print(f'{recv_time - prev_drop_time}s since last drop.', flush=True)
                    print()

                    drops += 1
                    prev_drop_time = recv_time
                    
                    # inserting None vec in-between current and previous vecs
                    rate /= 2
                    rates.append(np.nan)
                    vectors.append([np.nan]*50)

                rates.append(rate)
                vectors.append(vec)

                prev_recv_time = recv_time

                print(f'rate:{rate}', end = "\r", flush=True)

        except KeyboardInterrupt:
            print("received KeyboardInterrupt")
        finally:
            results = {}

            with open('results.json', 'w') as fp:
                results['rates'] = np.where(np.isnan(rates), None, rates).tolist()

                rates_analysis = {'mean': [], 'std': []}
                for i in range(0, len(rates), metrix_size):
                    a = rates[i:i + metrix_size]
                    rates_analysis['mean'].append(np.nanmean(a, axis=0).tolist())
                    rates_analysis['std'].append(np.nanstd(a, axis=0).tolist())

                results['rates_analysis'] = rates_analysis

                matrices = []
                for i in range(0, len(vectors), metrix_size):
                    matrices.append(vectors[i:i + metrix_size])

                data_analysis = {'mean': [], 'std': []}
                for matrix in np.array(matrices):
                    data_analysis['mean'].append(np.nanmean(matrix, axis=0).tolist())
                    data_analysis['std'].append(np.nanstd(matrix, axis=0).tolist())

                results['data_analysis'] = data_analysis

                json.dump(results, fp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--noisy_mode', action='store_true', required=True, help='Enable noisy mode')
    parser.add_argument('-s', '--series_size', type=int, required=True, help='Number of matrices (each matrix holds 100 vectors)')
    args = parser.parse_args()

    # TCP sockets work on any OS, but UNIX sockets (when supported) are faster
    # On my Win10 work laptop, UNIX sockets were significantly faster.
    if platform.system() == 'Windows':
        address = ('localhost', 30000)
    else:
        address = ('/tmp/socket')

    p1 = Process(target=sender, args=(address, args.noisy_mode))
    p1.start()

    p2 = Process(target=receiver, args=(address, args.noisy_mode, args.series_size))
    p2.start()

    try:
        p2.join()
    except KeyboardInterrupt:
        p2.terminate()
        p2.join()
    finally:
        p1.join()
