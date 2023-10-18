
import os
import subprocess
import csv
import configparser

def add_NPSH3(spro_files):

    with open(spro_files[0], "r") as infile:
        data = infile.readlines()
        for line in data:
            if "DPtt = " in line:
                inlet = line.split("\"")[3]

    addition = "\t\t\t#NPSH [m]" + "\n" + "\t\t\tplot.NPSH = (flow.mpt@\"" + inlet + "\" - p_vap)/rho/9.81" + "\n" + "\t\t\t#plot.NPSH:NPSH [m]" + "\n"

    with open(spro_files[0], 'r') as infile:
        data = infile.readlines()
        for line_number, line in enumerate(data):
            if "<expressions>" in line:
                domain_start = line_number + 1
            if "</expressions>" in line:
                domain_end = line_number

    exists_already = False

    with open(spro_files[0], 'r') as infile:
        data = infile.readlines()
        for line_number, line in enumerate(data[domain_start:domain_end]):
            if "=" in line:
                if addition.split("\n")[1].split("=")[1].strip() == line.split("=")[1].strip():
                    exists_already = True

    if exists_already == False:
        for spro_file in spro_files:
            with open(spro_file, 'r') as infile:
                data = infile.readlines()
                for line_number, line in enumerate(data):
                    if "</expressions>" in line and addition.split("=")[0] not in data[line_number + 1]:
                        data.insert(line_number, "\n" + addition + "\n")
                        break
            
            with open(spro_file, 'w') as outfile:
                data = "".join(data)
                outfile.write(data)

    return 0


def change_inlet_pressure(spro_files, inlet_pressures):

    new_spro_files = []

    for inlet_pressure in inlet_pressures:

        new_spro_pair = []

        for spro_file in spro_files:
            new_spro_file = spro_file.split(".")[0] + "_" + str(inlet_pressure).replace(".", "-") + "Pa.spro"
            new_spro_pair.append(new_spro_file)

            with open(spro_file, 'r') as infile, open(new_spro_file, 'w') as outfile:
                data = infile.readlines()
                for line in data:
                    if "pt_in = " in line:
                        outfile.write("\t\t\t" + "pt_in = " + str(inlet_pressure) + "\n")
                    else:
                        outfile.write(line)

        new_spro_files.append(tuple(new_spro_pair))

    return new_spro_files


def run_simerics(new_spro_files):

    for new_spro_pair in new_spro_files:
        if not os.path.exists(new_spro_pair[0].replace(".spro", ".sres")):

            with open("simerics.bat", "w") as batch:
                batch.truncate(0)
                simerics_command = "\"C:\Program Files\Simerics\SimericsMP.exe\" -run \"" + new_spro_pair[0] + \
                    "\"" + "\n" + "\"C:\Program Files\Simerics\SimericsMP.exe\" -run \"" + new_spro_pair[1] + "\" \"" + new_spro_pair[0].replace("transient", "steady").replace(".spro", ".sres") + "\"\n"
                batch.write(simerics_command)
                batch.close()

            subprocess.call(os.path.abspath("simerics.bat"))
        
    return 0


def post_process(new_spro_files, avg_window, inlet_pressures):

    for index, new_spro_pair in enumerate(new_spro_files):

        units_dict = {}
        descriptions_dict = {}

        with open(new_spro_pair[0], 'r') as infile:
            data = infile.readlines()
            for line in data:
                if "#plot." in line:
                    key = line.split(":")[0].split(".")[1].strip()
                    units_dict[key] = line.split(" ")[-1].strip() 
                    descriptions_dict[key] = line.split("[")[0].split(":")[1].strip()

        integrals_file = new_spro_pair[1].replace(".spro", "_integrals.txt")

        results_dict = {}
        
        result_Matrix = []

        with open(integrals_file, 'r') as infile:
            for row in list(infile):
                result_Matrix.append(row.split("\t"))

        result_Matrix_t = [list(x) for x in zip(*result_Matrix)]
        
        for row in result_Matrix_t:

            key = row[0]

            if key is not None and 'userdef.' in key:
                max_value = float(max(row[-avg_window:]))
                min_value = float(min(row[-avg_window:]))
                average_value = (max_value + min_value)/2.0
                results_dict[key[8:]] = average_value

        results_dict['pt_in'] = inlet_pressures[index]
        units_dict['pt_in'] = '[Pa]'
        descriptions_dict['pt_in'] = 'Inlet Pressure'

        order = ['pt_in', 'H', 'NPSH']

        for key in results_dict.keys():
            if key not in order:
                order.append(key)

        results_dict = {k: results_dict[k] for k in order}

        isFirst = True

        csv_file_name = project_name + '_cav_results_' + '.csv'

        if os.path.exists(csv_file_name):
            isFirst = False
            
        with open (csv_file_name, 'a+', newline='') as outfile:                             
            writer = csv.DictWriter(outfile, fieldnames=results_dict.keys(), delimiter=",")
            if isFirst == True:
                outfile.truncate(0)
                writer.writeheader()   
                writer.writerow(descriptions_dict)
                writer.writerow(units_dict)                                                                   
            writer.writerow(results_dict)

    return results_dict
    

def main():

    def Get_ConfigValue(ConfigSection, ConfigKey):                                                      
        ConfigValue = CFconfig[ConfigSection][ConfigKey]
        return ConfigValue

    CFconfig = configparser.ConfigParser()                                                             
    CFconfig.read("cavitation_breakdown_curve.cftconf")

    project_name = Get_ConfigValue("Project", "project_name")
    spro_files = (project_name + "_steady.spro", project_name + "_transient.spro")
    inlet_pressures = Get_ConfigValue("Inlet Pressures", "inlet_pressures").split(" ") 

    add_NPSH3(spro_files)
    new_spro_files = change_inlet_pressure(spro_files, inlet_pressures)
    run_simerics(new_spro_files)
    post_process(new_spro_files, 120, inlet_pressures)
    return 0

main()
