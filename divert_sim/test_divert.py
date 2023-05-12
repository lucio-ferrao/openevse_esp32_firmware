#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

from os import path
import os
from subprocess import PIPE, Popen
from datetime import datetime

OPENEVSE_STATE_STARTING = 0
OPENEVSE_STATE_NOT_CONNECTED = 1
OPENEVSE_STATE_CONNECTED = 2
OPENEVSE_STATE_CHARGING = 3
OPENEVSE_STATE_VENT_REQUIRED = 4
OPENEVSE_STATE_DIODE_CHECK_FAILED = 5
OPENEVSE_STATE_GFI_FAULT = 6
OPENEVSE_STATE_NO_EARTH_GROUND = 7
OPENEVSE_STATE_STUCK_RELAY = 8
OPENEVSE_STATE_GFI_SELF_TEST_FAILED = 9
OPENEVSE_STATE_OVER_TEMPERATURE = 0
OPENEVSE_STATE_OVER_CURRENT = 1
OPENEVSE_STATE_SLEEPING = 4
OPENEVSE_STATE_DISABLED = 5

KWH_ROUNDING = 2

def setup():
    """Create the output directory"""
    print("Setting up test environment")
    if not path.exists('output'):
        os.mkdir('output')
    with open(path.join('output', 'summary.csv'), 'w', encoding="utf-8") as summary_file:
        summary_file.write('"Dataset","Total Solar (kWh)","Total EV Charge (kWh)","Charge from solar (kWh)","Charge from grid (kWh)","Number of charges","Min time charging","Max time charging","Total time charging"\n')

def run_test_with_dataset(dataset: str,
                expected_solar_kwh:  float,
                expected_ev_kwh : float,
                expected_kwh_from_solar : float,
                expected_kwh_from_grid : float,
                expected_number_of_charges: int,
                expected_min_time_charging: int,
                expected_max_time_charging: int,
                expected_total_time_charging: int,
                config: bool = False, grid_ie_col: bool = False,
                solar_col: bool = False, voltage_col: bool = False,
                separator: str = ',', is_kw: bool = False) -> None:
    """Run the divert_sim process on the given dataset and return the results"""
    line_number = 0

    last_date = None
    last_state = 0
    charge_start_date = None

    total_solar_wh = 0
    total_ev_wh = 0
    wh_from_solar = 0
    wh_from_grid = 0
    number_of_charges = 0
    min_time_charging = 0
    max_time_charging = 0
    total_time_charging = 0

    print("Testing dataset: " + dataset)

    # Read in the dataset and pass to the divert_sim process
    with open(path.join('data', dataset+'.csv'), 'r', encoding="utf-8") as input_data:
        with open(path.join('output', dataset+'.csv'), 'w', encoding="utf-8") as output_data:
            # open the divert_sim process
            command = ["./divert_sim"]
            if config:
                command.append("-c")
                command.append(config)
            if grid_ie_col:
                command.append("-g")
                command.append(str(grid_ie_col))
            if solar_col:
                command.append("-s")
                command.append(str(solar_col))
            if voltage_col:
                command.append("-v")
                command.append(str(voltage_col))
            if separator:
                command.append("--sep")
                command.append(separator)
            if is_kw:
                command.append("--kw")

            divert_process = Popen(command, stdin=input_data, stdout=PIPE,
                    stderr=PIPE, universal_newlines=True)
            while True:
                output = divert_process.stdout.readline()
                if output == '' and divert_process.poll() is not None:
                    break
                if output:
                    output_data.write(output)
                    line_number += 1
                    if line_number > 1:
                        # read in the csv line
                        csv_line = output.split(',')
                        date = datetime.strptime(csv_line[0], '%d/%m/%Y %H:%M:%S')
                        solar = float(csv_line[1])
                        # grid_ie = float(csv_line[2])
                        # pilot = int(csv_line[3])
                        charge_power = float(csv_line[4])
                        # min_charge_power = float(csv_line[5])
                        state = int(csv_line[6])
                        # smoothed_available = float(csv_line[7])

                        if last_date is not None:
                            # Get the difference between this date and last date
                            diff = date - last_date

                            hours = diff.seconds / 3600

                            total_solar_wh += solar * hours
                            ev_wh = charge_power * hours
                            total_ev_wh += charge_power * hours
                            charge_from_solar_wh = min(solar, charge_power) * hours
                            wh_from_solar += charge_from_solar_wh
                            wh_from_grid += ev_wh - charge_from_solar_wh

                            if state == OPENEVSE_STATE_CHARGING and last_state != OPENEVSE_STATE_CHARGING:
                                number_of_charges += 1
                                charge_start_date = date

                            if state != OPENEVSE_STATE_CHARGING and last_state == OPENEVSE_STATE_CHARGING:
                                this_session_time_charging = (date - charge_start_date).seconds
                                total_time_charging += this_session_time_charging
                                if min_time_charging == 0 or this_session_time_charging < min_time_charging:
                                    min_time_charging = this_session_time_charging
                                if this_session_time_charging > max_time_charging:
                                    max_time_charging = this_session_time_charging

                        last_date = date
                        last_state = state

        solar_kwh=total_solar_wh / 1000
        ev_kwh=total_ev_wh / 1000
        kwh_from_solar=wh_from_solar / 1000
        kwh_from_grid=wh_from_grid / 1000

        with open(path.join('output', 'summary.csv'), 'a', encoding="utf-8") as summary_file:
            summary_file.write(f'"{dataset}",{solar_kwh},{ev_kwh},{kwh_from_solar},{kwh_from_grid},{number_of_charges},{min_time_charging},{max_time_charging},{total_time_charging}\n')

        assert round(solar_kwh, KWH_ROUNDING) == expected_solar_kwh
        assert round(ev_kwh, KWH_ROUNDING) == expected_ev_kwh
        assert round(kwh_from_solar, KWH_ROUNDING) == expected_kwh_from_solar
        assert round(kwh_from_grid, KWH_ROUNDING) == expected_kwh_from_grid
        assert number_of_charges == expected_number_of_charges
        assert min_time_charging == expected_min_time_charging
        assert max_time_charging == expected_max_time_charging
        assert total_time_charging == expected_total_time_charging

def test_divert_almostperfect() -> None:
    """Run the divert test with the almostperfect dataset"""
    run_test_with_dataset('almostperfect',
                21.08, 17.24, 17.05, 0.19, 1, 30060, 30060, 30060)

def test_divert_CloudyMorning() -> None:
    """Run the divert test with the CloudyMorning dataset"""
    run_test_with_dataset('CloudyMorning',
                16.64, 13.03, 12.67, 0.36, 1, 22200, 22200, 22200)

def test_divert_day1() -> None:
    """Run the divert test with the day1 dataset"""
    run_test_with_dataset('day1',
                10.12, 7.48, 6.71, 0.77, 5, 660, 10080, 13740)

def test_divert_day2() -> None:
    """Run the divert test with the day2 dataset"""
    run_test_with_dataset('day2',
                12.35, 9.88, 9.86, 0.02, 1, 19920, 19920, 19920)

def test_divert_day3() -> None:
    """Run the divert test with the day3 dataset"""
    run_test_with_dataset('day3',
                5.09, 2.22, 1.60, 0.62, 5, 660, 2400, 5340)

def test_divert_day1_grid_ie() -> None:
    """Run the divert test with the day1_grid_ie dataset"""
    run_test_with_dataset('day1_grid_ie',
                15.13, 8.83, 8.47, 0.36, 5, 660, 7800, 19860,
                grid_ie_col=2)

def test_divert_day2_grid_ie() -> None:
    """Run the divert test with the day2_grid_ie dataset"""
    run_test_with_dataset('day2_grid_ie',
                10.85, 7.66, 6.16, 1.50, 10, 420, 7980, 16260,
                grid_ie_col=2)

def test_divert_day3_grid_ie() -> None:
    """Run the divert test with the day3_grid_ie dataset"""
    run_test_with_dataset('day3_grid_ie',
                12.13, 6.32, 6.27, 0.05, 2, 3660, 9840, 13500,
                grid_ie_col=2)

def test_divert_solar_vrms() -> None:
    """Run the divert test with the solar-vrms dataset"""
    run_test_with_dataset('solar-vrms',
                13.85, 12.26, 12.10, 0.17, 1, 22080, 22080, 22080,
                voltage_col=2)

def test_divert_Energy_and_Power_Day_2020_03_22() -> None:
    """Run the divert test with the Energy_and_Power_Day_2020-03-22 dataset"""
    run_test_with_dataset('Energy_and_Power_Day_2020-03-22',
                41.87, 38.52, 38.41, 0.11, 1, 28800, 28800, 28800,
                separator=';', is_kw=True, config='{"divert_decay_smoothing_factor":0.4}')

def test_divert_Energy_and_Power_Day_2020_03_31() -> None:
    """Run the divert test with the Energy_and_Power_Day_2020-03-31 dataset"""
    run_test_with_dataset('Energy_and_Power_Day_2020-03-31',
                23.91, 18.78, 18.66, 0.12, 1, 22500, 22500, 22500,
                separator=';', is_kw=True, config='{"divert_decay_smoothing_factor":0.4}')

def test_divert_Energy_and_Power_Day_2020_04_01() -> None:
    """Run the divert test with the Energy_and_Power_Day_2020-04-01 dataset"""
    run_test_with_dataset('Energy_and_Power_Day_2020-04-01',
                38.89, 36.72, 36.41, 0.32, 1, 27000, 27000, 27000,
                separator=';', is_kw=True, config='{"divert_decay_smoothing_factor":0.4}')

if __name__ == '__main__':
    # Run the script
    test_divert_almostperfect()
    test_divert_CloudyMorning()
    test_divert_day1()
    test_divert_day2()
    test_divert_day3()
    test_divert_day1_grid_ie()
    test_divert_day2_grid_ie()
    test_divert_day3_grid_ie()
    test_divert_solar_vrms()
    test_divert_Energy_and_Power_Day_2020_03_22()
    test_divert_Energy_and_Power_Day_2020_03_31()
    test_divert_Energy_and_Power_Day_2020_04_01()