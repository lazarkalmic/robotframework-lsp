package robocorp.robot.intellij;

import com.intellij.openapi.options.Configurable;
import com.intellij.openapi.options.ConfigurationException;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.NlsContexts;
import com.intellij.ui.components.JBLabel;
import com.intellij.ui.components.JBTextArea;
import com.intellij.ui.components.JBTextField;
import com.intellij.util.ui.FormBuilder;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import robocorp.lsp.intellij.LanguageServerDefinition;

import javax.swing.*;


// IMPORTANT: Autogenerated. Don't change manually. Run codegen.py to regenerate.
class RobotPreferencesComponent {

    private final JPanel panel;
    
    private final JBTextField robotLanguageServerPython = new JBTextField();
    private final JBTextField robotLanguageServerArgs = new JBTextField();
    private final JBTextField robotLanguageServerTcpPort = new JBTextField();
    private final JBTextField robotPythonExecutable = new JBTextField();
    private final JBTextField robotPythonEnv = new JBTextField();
    private final JBTextField robotVariables = new JBTextField();
    private final JBTextField robotPythonpath = new JBTextField();
    private final JBTextField robotCompletionsSectionHeadersForm = new JBTextField();
    private final JBTextField robotWorkspaceSymbolsOnlyForOpenDocs = new JBTextField();

    public RobotPreferencesComponent() {
        panel = FormBuilder.createFormBuilder()
                .addLabeledComponent(new JBLabel("Language Server Python"), robotLanguageServerPython, 1, false)
                .addComponent(createJTextArea("Specifies the path to the python executable to be used for the Robot Framework Language Server (the default is searching python on the PATH).\n"))
                .addLabeledComponent(new JBLabel("Language Server Args"), robotLanguageServerArgs, 1, false)
                .addComponent(createJTextArea("Specifies the arguments to be passed to the robotframework language server (i.e.: [\"-vv\", \"--log-file=~/robotframework_ls.log\"]).\nNote: expected format: JSON Array\n"))
                .addLabeledComponent(new JBLabel("Language Server Tcp Port"), robotLanguageServerTcpPort, 1, false)
                .addComponent(createJTextArea("If the port is specified, connect to the language server previously started at the given port.\n"))
                .addLabeledComponent(new JBLabel("Python Executable"), robotPythonExecutable, 1, false)
                .addComponent(createJTextArea("Specifies the path to the python executable to be used to load `robotframework` code and dependent libraries (the default is using the same python\nused for the language server).\n"))
                .addLabeledComponent(new JBLabel("Python Env"), robotPythonEnv, 1, false)
                .addComponent(createJTextArea("Specifies the environment to be used when loading `robotframework` code and dependent libraries.i.e.: {\"MY_ENV_VAR\": \"some_value\"}\nNote: expected format: JSON Object\n"))
                .addLabeledComponent(new JBLabel("Variables"), robotVariables, 1, false)
                .addComponent(createJTextArea("Specifies custom variables to be considered by `robotframework` (used when resolving variables and automatically passed to the launch config as\n--variable entries).i.e.: {\"RESOURCES\": \"c:/temp/resources\"}\nNote: expected format: JSON Object\n"))
                .addLabeledComponent(new JBLabel("Pythonpath"), robotPythonpath, 1, false)
                .addComponent(createJTextArea("Specifies the entries to be added to the PYTHONPATH (used when resolving resources and imports and automatically passed to the launch config as\n--pythonpath entries).i.e.: [\"</my/path_entry>\"]\nNote: expected format: JSON Array\n"))
                .addLabeledComponent(new JBLabel("Completions Section Headers Form"), robotCompletionsSectionHeadersForm, 1, false)
                .addComponent(createJTextArea("Defines how completions should be shown for section headers (i.e.: *** Setting(s) ***).One of: plural, singular, both.\n"))
                .addLabeledComponent(new JBLabel("Workspace Symbols Only For Open Docs"), robotWorkspaceSymbolsOnlyForOpenDocs, 1, false)
                .addComponent(createJTextArea("Collecting workspace symbols can be resource intensive on big projects and may slow down code-completion, in this case, it's possible collect info\nonly for open files on big projects.\n"))
                
                .addComponentFillVertically(new JPanel(), 0)
                .getPanel();
    }

    private JBTextArea createJTextArea(String text) {
        JBTextArea f = new JBTextArea();
        f.setText(text);
        f.setEditable(false);
        f.setBackground(null);
        f.setBorder(null);
        f.setFont(UIManager.getFont("Label.font"));
        return f;
    }

    public JPanel getPanel() {
        return panel;
    }

    public JComponent getPreferredFocusedComponent() {
        return robotLanguageServerPython;
    }

    
    @NotNull
    public String getRobotLanguageServerPython() {
        return robotLanguageServerPython.getText();
    }

    public void setRobotLanguageServerPython (@NotNull String newText) {
        robotLanguageServerPython.setText(newText);
    }
    
    @NotNull
    public String getRobotLanguageServerArgs() {
        return robotLanguageServerArgs.getText();
    }

    public void setRobotLanguageServerArgs (@NotNull String newText) {
        robotLanguageServerArgs.setText(newText);
    }
    
    @NotNull
    public String getRobotLanguageServerTcpPort() {
        return robotLanguageServerTcpPort.getText();
    }

    public void setRobotLanguageServerTcpPort (@NotNull String newText) {
        robotLanguageServerTcpPort.setText(newText);
    }
    
    @NotNull
    public String getRobotPythonExecutable() {
        return robotPythonExecutable.getText();
    }

    public void setRobotPythonExecutable (@NotNull String newText) {
        robotPythonExecutable.setText(newText);
    }
    
    @NotNull
    public String getRobotPythonEnv() {
        return robotPythonEnv.getText();
    }

    public void setRobotPythonEnv (@NotNull String newText) {
        robotPythonEnv.setText(newText);
    }
    
    @NotNull
    public String getRobotVariables() {
        return robotVariables.getText();
    }

    public void setRobotVariables (@NotNull String newText) {
        robotVariables.setText(newText);
    }
    
    @NotNull
    public String getRobotPythonpath() {
        return robotPythonpath.getText();
    }

    public void setRobotPythonpath (@NotNull String newText) {
        robotPythonpath.setText(newText);
    }
    
    @NotNull
    public String getRobotCompletionsSectionHeadersForm() {
        return robotCompletionsSectionHeadersForm.getText();
    }

    public void setRobotCompletionsSectionHeadersForm (@NotNull String newText) {
        robotCompletionsSectionHeadersForm.setText(newText);
    }
    
    @NotNull
    public String getRobotWorkspaceSymbolsOnlyForOpenDocs() {
        return robotWorkspaceSymbolsOnlyForOpenDocs.getText();
    }

    public void setRobotWorkspaceSymbolsOnlyForOpenDocs (@NotNull String newText) {
        robotWorkspaceSymbolsOnlyForOpenDocs.setText(newText);
    }
    

}

// IMPORTANT: Autogenerated. Don't change manually. Run codegen.py to regenerate.
public class RobotPreferencesPage implements Configurable {
    
    private RobotPreferencesComponent component;

    @Override
    public @NlsContexts.ConfigurableName String getDisplayName() {
        return "Robot Framework (Global)";
    }

    @Override
    public JComponent getPreferredFocusedComponent() {
        return component.getPreferredFocusedComponent();
    }

    @Override
    public @Nullable JComponent createComponent() {
        component = new RobotPreferencesComponent();
        return component.getPanel();
    }

    @Override
    public boolean isModified() {
        RobotPreferences settings = RobotPreferences.getInstance();
        
        if(!settings.getRobotLanguageServerPython().equals(component.getRobotLanguageServerPython())){
            return true;
        }
        
        if(!settings.getRobotLanguageServerArgs().equals(component.getRobotLanguageServerArgs())){
            return true;
        }
        
        if(!settings.getRobotLanguageServerTcpPort().equals(component.getRobotLanguageServerTcpPort())){
            return true;
        }
        
        if(!settings.getRobotPythonExecutable().equals(component.getRobotPythonExecutable())){
            return true;
        }
        
        if(!settings.getRobotPythonEnv().equals(component.getRobotPythonEnv())){
            return true;
        }
        
        if(!settings.getRobotVariables().equals(component.getRobotVariables())){
            return true;
        }
        
        if(!settings.getRobotPythonpath().equals(component.getRobotPythonpath())){
            return true;
        }
        
        if(!settings.getRobotCompletionsSectionHeadersForm().equals(component.getRobotCompletionsSectionHeadersForm())){
            return true;
        }
        
        if(!settings.getRobotWorkspaceSymbolsOnlyForOpenDocs().equals(component.getRobotWorkspaceSymbolsOnlyForOpenDocs())){
            return true;
        }
        
        return false;
    }

    @Override
    public void reset() {
        RobotPreferences settings = RobotPreferences.getInstance();
        
        component.setRobotLanguageServerPython(settings.getRobotLanguageServerPython());
        component.setRobotLanguageServerArgs(settings.getRobotLanguageServerArgs());
        component.setRobotLanguageServerTcpPort(settings.getRobotLanguageServerTcpPort());
        component.setRobotPythonExecutable(settings.getRobotPythonExecutable());
        component.setRobotPythonEnv(settings.getRobotPythonEnv());
        component.setRobotVariables(settings.getRobotVariables());
        component.setRobotPythonpath(settings.getRobotPythonpath());
        component.setRobotCompletionsSectionHeadersForm(settings.getRobotCompletionsSectionHeadersForm());
        component.setRobotWorkspaceSymbolsOnlyForOpenDocs(settings.getRobotWorkspaceSymbolsOnlyForOpenDocs());
    }

    @Override
    public void apply() throws ConfigurationException {
        RobotPreferences settings = RobotPreferences.getInstance();
        String s;
        
        s = settings.validateRobotLanguageServerPython(component.getRobotLanguageServerPython());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Language Server Python:\n" + s);
        }
        s = settings.validateRobotLanguageServerArgs(component.getRobotLanguageServerArgs());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Language Server Args:\n" + s);
        }
        s = settings.validateRobotLanguageServerTcpPort(component.getRobotLanguageServerTcpPort());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Language Server Tcp Port:\n" + s);
        }
        s = settings.validateRobotPythonExecutable(component.getRobotPythonExecutable());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Python Executable:\n" + s);
        }
        s = settings.validateRobotPythonEnv(component.getRobotPythonEnv());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Python Env:\n" + s);
        }
        s = settings.validateRobotVariables(component.getRobotVariables());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Variables:\n" + s);
        }
        s = settings.validateRobotPythonpath(component.getRobotPythonpath());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Pythonpath:\n" + s);
        }
        s = settings.validateRobotCompletionsSectionHeadersForm(component.getRobotCompletionsSectionHeadersForm());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Completions Section Headers Form:\n" + s);
        }
        s = settings.validateRobotWorkspaceSymbolsOnlyForOpenDocs(component.getRobotWorkspaceSymbolsOnlyForOpenDocs());
        if(!s.isEmpty()) {
            throw new ConfigurationException("Error in Workspace Symbols Only For Open Docs:\n" + s);
        }
        
        settings.setRobotLanguageServerPython(component.getRobotLanguageServerPython());
        settings.setRobotLanguageServerArgs(component.getRobotLanguageServerArgs());
        settings.setRobotLanguageServerTcpPort(component.getRobotLanguageServerTcpPort());
        settings.setRobotPythonExecutable(component.getRobotPythonExecutable());
        settings.setRobotPythonEnv(component.getRobotPythonEnv());
        settings.setRobotVariables(component.getRobotVariables());
        settings.setRobotPythonpath(component.getRobotPythonpath());
        settings.setRobotCompletionsSectionHeadersForm(component.getRobotCompletionsSectionHeadersForm());
        settings.setRobotWorkspaceSymbolsOnlyForOpenDocs(component.getRobotWorkspaceSymbolsOnlyForOpenDocs());
    }
}